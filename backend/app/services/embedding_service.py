import time
import math
from typing import List, Optional, Generator, Tuple

from ..config import settings


class EmbeddingService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = settings.EMBEDDING_MODEL
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured. Please set GEMINI_API_KEY in .env or environment.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generates embedding for a single user query.
        """
        client = self._get_client()
        try:
            response = client.models.embed_content(
                model=self.model,
                contents=query,
            )
            # Response contains embeddings list
            if response.embeddings and len(response.embeddings) > 0:
                return response.embeddings[0].values
            raise ValueError("No embeddings returned by Gemini API")
        except Exception as e:
            # Check for common errors
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "403" in err_msg:
                raise ValueError("Invalid GEMINI_API_KEY. Please check your Gemini API key.")
            raise RuntimeError(f"Failed to generate query embedding: {e}")

    def generate_embeddings_stream(self, texts: List[str]) -> Generator[Tuple[int, List[float]], None, None]:
        """
        Generator that yields (index, embedding_vector) tuples one at a time.
        This allows the caller to track real-time progress during embedding generation.
        """
        if not texts:
            return

        client = self._get_client()

        for idx, text in enumerate(texts):
            max_retries = 5
            backoff = 10

            for attempt in range(max_retries):
                try:
                    response = client.models.embed_content(
                        model=self.model,
                        contents=text,
                    )
                    if response.embeddings and len(response.embeddings) > 0:
                        yield (idx, response.embeddings[0].values)

                        # Small delay to avoid burst limits
                        time.sleep(1)
                        break
                    else:
                        raise ValueError("Empty embeddings response from Gemini API")
                except Exception as e:
                    err_str = str(e)
                    if attempt == max_retries - 1:
                        raise RuntimeError(f"Embedding failed after {max_retries} attempts for chunk {idx}: {e}")

                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        # Rate limit hit, wait longer
                        time.sleep(backoff)
                        backoff *= 2
                    else:
                        time.sleep(2)

    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 15) -> List[List[float]]:
        """
        Non-streaming wrapper around generate_embeddings_stream for backward compatibility.
        """
        all_embeddings: List[List[float]] = []
        for idx, embedding in self.generate_embeddings_stream(texts):
            all_embeddings.append(embedding)
        return all_embeddings
