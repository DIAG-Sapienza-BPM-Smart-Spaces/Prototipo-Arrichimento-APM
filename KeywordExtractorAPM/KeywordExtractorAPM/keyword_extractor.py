import json
import re
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
import config

MAX_TEXT_LENGTH = 2000

class Extractor:
    def __init__(self):
        self.llm = OllamaLLM(
            model=config.OLLAMA_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            temperature=config.TEMPERATURE,
            format="json",
        )

        # STAGE 1: Free Extraction and Understanding (Chain of Thought)
        prompt_stage_1 = """Sei un tecnico esperto. Leggi il seguente rapporto di manutenzione autobus e analizzalo liberamente.
Non sei limitato a nessuna lista predefinita. Spiega cosa è successo.

Testo originale: {text}
Suggerimento materiale: {material_hint}

Rispondi in formato JSON con questi campi:
- "analisi": (string) Spiega brevemente il problema e l'intervento.
- "sintomo_libero": (string) Qual era il problema o sintomo?
- "sistema_libero": (string) Quale sistema o macro-area è stata riparata?
- "azione_libera": (string) Che azioni sono state fatte (es. sostituito, pulito, smontato)?
- "pezzi_coinvolti": (string) Elenca i nomi di tutti i pezzi menzionati, in ITALIANO pulito. Se e' fornito un materiale (anche in un'altra lingua), e' il pezzo ufficiale: traducilo in italiano e includilo.
- "luogo": (string) Dove è successo il guasto o dove è stato notato? Estrai il nome del luogo SOLO se indica dove è avvenuto/notato il guasto (es. AEROPORTO FIUMICINO, CASSINO). Ignora frasi di routine come "prelievo dal deposito" o "posizionamento in stallo". (Se non menzionato: N/A)
- "esito_libero": (string) Il testo dichiara ESPLICITAMENTE l'esito? Riporta solo ciò che è scritto ("positivo", "in attesa", "ancora guasto"). Se l'esito NON è dichiarato nel testo, scrivi "NON_SPECIFICATO". Non dare per scontato il successo.

JSON:
"""
        self.prompt_1 = PromptTemplate(
            template=prompt_stage_1,
            input_variables=["text", "material_hint"],
        )

        # STAGE 2: Mapping to Taxonomy — Enriched with K-rules principle + few-shot
        prompt_stage_2 = """Sei un classificatore esperto di dati di manutenzione autobus. Ti verrà fornita un'analisi libera di un guasto. Mappa le informazioni alla Tassonomia Ufficiale seguendo RIGOROSAMENTE i principi qui sotto.

=== ANALISI LIBERA ===
{free_analysis}

=== TASSONOMIA UFFICIALE ===
TIPO INTERVENTO: {tipo_intervento_values}
SINTOMO: {sintomo_values}
SISTEMA: {sistema_values}
AZIONE: {azione_values}
ESITO: {esito_values}

=== PRINCIPI DI CLASSIFICAZIONE (OBBLIGATORI) ===

[SISTEMA - principio della causa radice]
- SISTEMA = il sistema funzionale dove risiede il guasto, NON la tecnologia del pezzo.
- Un sensore/centralina/attuatore elettronico che SERVE un sistema specifico appartiene a QUEL sistema, non a IMPIANTO_ELETTRICO.
  Esempi: sensore NOx o filtro DPF -> SCARICO. Centralina A/C -> CLIMATIZZAZIONE. Galleggiante/sensore AdBlue -> ADBLUE. Pompa acqua -> RAFFREDDAMENTO.
- USA IMPIANTO_ELETTRICO SOLO se il guasto è nell'impianto elettrico stesso: cablaggi, connettori, fusibili, batteria, cortocircuito.
- Manutenzione programmata senza sistema specifico -> GENERALE.

[SINTOMO - basato sul sintomo riportato]
- SINTOMO = il problema RIPORTATO (come descritto in cima al testo), non la causa radice diagnosticata.
- Pneumatico bucato/forato/danneggiato -> GUASTO_MECCANICO (NON perdita_aria: quella è solo per l'impianto pneumatico freni/sospensioni).
- "Limite potenza motore" / perdita di potenza -> NON_ACCELERA.
- Una spia accesa -> SPIA_ACCESA, TRANNE quando indica direttamente un guasto elettrico/comunicazione (es. spia PCAN con connettore ossidato) -> GUASTO_ELETTRICO.
- Manutenzione programmata (T1, T2, tagliando) -> NESSUN_GUASTO.

[AZIONE - estrai TUTTE le azioni significative]
- Restituisci TUTTE le azioni significative separate da virgola, non solo una.
- DIAGNOSI = diagnosi elettronica, lettura/cancellazione errori/codici nella centralina (lascia traccia digitale nell'ECU).
- CONTROLLO = ispezione fisica/visiva, ricerca guasto o perdite fatta manualmente (senza ECU).
- RABBOCCO = rabbocco liquido, carica/ricarica gas, aggiunta olio.
- NON etichettare smontaggio/rimontaggio (S/R) se serve solo ad ACCEDERE a un altro pezzo. Etichetta SMONTAGGIO_RIMONTAGGIO SOLO se è il lavoro principale (nessuna sostituzione/riparazione presente).
- Distingui SOSTITUZIONE (cambio pezzo) da RIPARAZIONE (aggiustare pezzo esistente).

[ESITO - solo con prova esplicita]
- POSITIVO solo se il testo dichiara ESPLICITAMENTE il successo: "positivo/positiva", "problema risolto", "funzionante", "prova ok".
- Se il testo NON dichiara l'esito (anche se il lavoro sembra finito) -> NON_SPECIFICATO. NON dare per scontato il successo.
- "in attesa ricambi/da completare" -> IN_ATTESA. "ancora guasto/non risolto" -> NEGATIVO.

=== ESEMPI ===
Esempio 1 - Testo: "pneumatico bucato, sostituzione gomma con ruota di scorta"
-> sintomo: GUASTO_MECCANICO, sistema: PNEUMATICI, azione: SOSTITUZIONE, esito: NON_SPECIFICATO
Esempio 2 - Testo: "spia motore accesa, effettuata diagnosi, sostituzione sensore NOx, prova positiva"
-> sintomo: SPIA_ACCESA, sistema: SCARICO, azione: DIAGNOSI, SOSTITUZIONE, esito: POSITIVO
Esempio 3 - Testo: "manutenzione T1"
-> sintomo: NESSUN_GUASTO, sistema: GENERALE, azione: MANUTENZIONE_PROGRAMMATA, esito: NON_SPECIFICATO

=== REGOLE FORMATO ===
1. Per i campi chiusi (tipo, sintomo, sistema, azione, esito) scegli SOLO valori esatti dalla Tassonomia.
2. Per COMPONENTE: estrai i nomi dei pezzi in ITALIANO pulito; se un pezzo e' indicato in un'altra lingua, traducilo in italiano.
3. Più valori separati da virgola dove appropriato.
4. Se nessuna corrispondenza logica per un campo chiuso, usa "ALTRO".

Genera SOLO un JSON in questo formato esatto:
{{
  "kw_luogo": "...",
  "kw_tipo_intervento": "...",
  "kw_sintomo": "...",
  "kw_sistema": "...",
  "kw_azione": "...",
  "kw_componente": "...",
  "kw_esito": "..."
}}
JSON:
"""
        self.prompt_2 = PromptTemplate(
            template=prompt_stage_2,
            input_variables=[
                "free_analysis", "tipo_intervento_values", 
                "sintomo_values", "sistema_values", 
                "azione_values", "esito_values"
            ],
        )

    def extract_stage_1(self, cleaned_text: str, material_hint: dict) -> dict:
        """Step 1: LLM freely analyzes the text."""
        truncated = cleaned_text[:MAX_TEXT_LENGTH] if len(cleaned_text) > MAX_TEXT_LENGTH else cleaned_text
        hint_str = json.dumps(material_hint) if material_hint else "Nessun suggerimento."

        formatted_prompt = self.prompt_1.format(text=truncated, material_hint=hint_str)
        return self._safe_invoke(formatted_prompt, "Stage 1")

    def extract_stage_2(self, free_analysis: dict, taxonomy: dict) -> dict:
        """Step 2: Free analysis results are mapped to the taxonomy."""
        def get_values(key):
            if key in taxonomy and "values" in taxonomy[key]:
                return " | ".join(taxonomy[key]["values"])
            return ""

        formatted_prompt = self.prompt_2.format(
            free_analysis=json.dumps(free_analysis, indent=2),
            tipo_intervento_values=get_values("tipo_intervento"),
            sintomo_values=get_values("sintomo"),
            sistema_values=get_values("sistema"),
            azione_values=get_values("azione"),
            esito_values=get_values("esito"),
        )
        
        result = self._safe_invoke(formatted_prompt, "Stage 2")
        
        # Check the keys of the results (must start with kw_)
        final_result = {}
        for col in config.KEYWORD_COLUMNS:
            if col == "kw_confidence":
                continue
            final_result[col] = str(result.get(col, "N/A")).strip().upper()
        return final_result

    def _safe_invoke(self, prompt: str, stage_name: str) -> dict:
        last_error = None
        for attempt in range(config.MAX_RETRIES):
            try:
                raw_response = self.llm.invoke(prompt)
                return self._parse_response(raw_response)
            except Exception as e:
                last_error = e
                if attempt < config.MAX_RETRIES - 1:
                    print(f"  [{stage_name}] Attempt {attempt + 1} failed... ({e})")
        
        print(f"  [{stage_name}] LLM failed: {last_error}")
        return {}

    def _parse_response(self, raw_response: str) -> dict:
        text = re.sub(r"```json\s*", "", raw_response)
        text = re.sub(r"```\s*", "", text).strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("JSON not found.")

        return json.loads(text[start : end + 1])
