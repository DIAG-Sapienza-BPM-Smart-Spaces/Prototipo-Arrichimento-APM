"""Client intercambiabili con le interfacce invoke ed embed_query."""

import os
import config


def _openai_client():
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise ValueError("Per OpenAI impostare la variabile d'ambiente OPENAI_API_KEY.")
    from openai import OpenAI
    return OpenAI(timeout=config.OPENAI_TIMEOUT, max_retries=2)


class OpenAIJsonLLM:
    def __init__(self):
        self.client = _openai_client()

    def invoke(self, prompt):
        response = self.client.responses.create(
            model=config.OPENAI_MODEL,
            instructions="Rispondi esclusivamente con un oggetto JSON valido.",
            input=prompt,
            text={"format": {"type": "json_object"}},
            store=False,
        )
        if response.status != "completed" or not response.output_text:
            raise ValueError("OpenAI non ha restituito una risposta completa con testo JSON.")
        return response.output_text


class OpenAIEmbeddingClient:
    def __init__(self):
        self.client = _openai_client()

    def embed_query(self, text):
        response = self.client.embeddings.create(
            model=config.OPENAI_EMBEDDING_MODEL,
            input=text,
            encoding_format="float",
        )
        return response.data[0].embedding


def create_llm():
    if config.LLM_PROVIDER == "openai":
        return OpenAIJsonLLM()
    from langchain_ollama import OllamaLLM
    return OllamaLLM(
        model=config.OLLAMA_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        temperature=config.TEMPERATURE,
        format="json",
    )


def create_embeddings():
    if config.EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddingClient()
    from langchain_ollama import OllamaEmbeddings
    return OllamaEmbeddings(
        model=config.OLLAMA_EMBEDDING_MODEL,
        base_url=config.OLLAMA_BASE_URL,
    )
