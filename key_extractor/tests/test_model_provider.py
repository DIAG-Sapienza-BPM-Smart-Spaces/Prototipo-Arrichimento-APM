"""Test offline: nessuna chiamata API e nessuna chiave reale."""

from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model_provider


class ProviderTests(unittest.TestCase):
    def test_missing_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                model_provider._openai_client()

    def test_openai_json_response_is_a_string(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            status="completed", output_text='{"sistema": "FRENI"}'
        )
        with patch.object(model_provider, "_openai_client", return_value=client):
            llm = model_provider.OpenAIJsonLLM()
        self.assertEqual(llm.invoke("rapporto"), '{"sistema": "FRENI"}')
        arguments = client.responses.create.call_args.kwargs
        self.assertEqual(arguments["text"], {"format": {"type": "json_object"}})
        self.assertFalse(arguments["store"])

    def test_incomplete_response_is_rejected(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            status="incomplete", output_text='{"sistema":'
        )
        with patch.object(model_provider, "_openai_client", return_value=client):
            llm = model_provider.OpenAIJsonLLM()
        with self.assertRaises(ValueError):
            llm.invoke("rapporto")

    def test_embedding_returns_vector(self):
        client = Mock()
        client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2])]
        )
        with patch.object(model_provider, "_openai_client", return_value=client):
            embedder = model_provider.OpenAIEmbeddingClient()
        self.assertEqual(embedder.embed_query("freni"), [0.1, 0.2])

    def test_provider_selection(self):
        with patch.object(model_provider.config, "LLM_PROVIDER", "openai"):
            with patch.object(model_provider, "OpenAIJsonLLM") as factory:
                self.assertIs(model_provider.create_llm(), factory.return_value)
        with patch.object(model_provider.config, "EMBEDDING_PROVIDER", "openai"):
            with patch.object(model_provider, "OpenAIEmbeddingClient") as factory:
                self.assertIs(model_provider.create_embeddings(), factory.return_value)


if __name__ == "__main__":
    unittest.main()
