import pandas as pd
from tqdm import tqdm
import config
from router import Router
from pathlib import Path
import warnings

# To hide Pandas warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

def setup_directories():
    config.INPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    setup_directories()
    
    # Find the first Excel/CSV file in the Input folder (for automatic retrieval)
    input_files = list(config.INPUT_DIR.glob("*.xlsx")) + list(config.INPUT_DIR.glob("*.csv"))
    
    if not input_files:
        print(f"Please place the excel or csv file to be processed into the '{config.INPUT_DIR}' folder.")
        return
        
    input_path = input_files[0]
    output_path = config.OUTPUT_DIR / f"processed_{input_path.name}"
    
    print(f"Reading file [{input_path.name}]...")
    if input_path.suffix == '.csv':
        df = pd.read_csv(input_path, low_memory=False)
    else:
        df = pd.read_excel(input_path)
        
    router = Router()
    
    # Add KEYWORD columns to df
    for col in config.KEYWORD_COLUMNS:
        if col not in df.columns:
            df[col] = None
            
    print("Natural Language Processing (NLP) process is starting...")
    
    # Iterate over all rows (with Progress Bar)
    for index, row in tqdm(df.iterrows(), total=len(df)):
        testo_breve = str(row.get(config.COL_DESCRIPTION, ""))
        
        # In the added CSV, material columns go as "materiale /Definizione 1", "2" etc.
        # Trying to catch the first non-empty material column.
        material_cols = [c for c in df.columns if str(c).startswith(config.COL_MATERIAL_PREFIX)]
        material_vals = [str(row[c]) for c in material_cols if pd.notna(row[c]) and str(row[c]).strip() != ""]
        
        # Send to Router (Cache -> Material -> LLM)
        result = router.process_row(testo_breve, material_vals)
        
        # Write the output result to DataFrame
        for key, value in result.items():
            if key in config.KEYWORD_COLUMNS:
                df.at[index, key] = value
                
        # Periodically save learned mappings to JSON (to avoid data loss if the program crashes)
        if (index + 1) % config.BATCH_SAVE_INTERVAL == 0:
            router.save_mappings()
            
    # Save one last time when the loop ends
    router.save_mappings()
    
    # --- NEWLY ADDED PART: Beautifying and Sorting Column Names ---
    print("Reorganizing Excel columns...")
    
    # 1. Rename kw_ columns to "TestoBreve_" for reader comprehension
    rename_map = {
        "kw_luogo": "TestoBreve_Luogo",
        "kw_tipo_intervento": "TestoBreve_TipoIntervento",
        "kw_sintomo": "TestoBreve_Sintomo",
        "kw_sistema": "TestoBreve_Sistema",
        "kw_azione": "TestoBreve_Azione",
        "kw_componente": "TestoBreve_Componente",
        "kw_esito": "TestoBreve_Esito",
        "kw_confidence": "TestoBreve_AI_Confidence"
    }
    df.rename(columns=rename_map, inplace=True)
    new_keyword_cols = list(rename_map.values())
    
    current_cols = list(df.columns)
    
    # Remove these new columns from their current position (far right)
    for k in new_keyword_cols:
        if k in current_cols:
            current_cols.remove(k)
            
    # Find the original Testo Breve column
    if config.COL_DESCRIPTION in current_cols:
        desc_idx = current_cols.index(config.COL_DESCRIPTION)
        
        # DATA ENGINEERING GOLDEN RULE: Do not delete original data, rename it to "Originale"!
        yeni_orijinal_ad = f"{config.COL_DESCRIPTION} (Originale)"
        df.rename(columns={config.COL_DESCRIPTION: yeni_orijinal_ad}, inplace=True)
        current_cols[desc_idx] = yeni_orijinal_ad
        
        # New Sorting: INCLUDING the original text, new analysis columns will be added immediately to its RIGHT
        final_cols = current_cols[:desc_idx+1] + new_keyword_cols + current_cols[desc_idx+1:]
        df = df[final_cols]
    # ------------------------------------------------------------------------
    
    # Export the file
    print("Saving file...")
    if output_path.suffix == '.csv':
        df.to_csv(output_path, index=False)
    else:
        df.to_excel(output_path, index=False)
        
    print(f"Process Completed! Output directory: {output_path}")

    # --- Confidence summary (no separate review file) ---
    # The confidence column stays in the output; low-confidence rows can be
    # inspected manually in the Excel by filtering TestoBreve_AI_Confidence.
    conf_col = "TestoBreve_AI_Confidence"
    if conf_col in df.columns:
        dist = df[conf_col].astype(str).str.upper().value_counts().to_dict()
        print(f"[CONFIDENCE] Distribution: {dist}")

if __name__ == "__main__":
    main()
