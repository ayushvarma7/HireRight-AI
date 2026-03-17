"""
Embedding Service

Generate embeddings using Google Gemini for semantic search.
"""

from typing import List
import time
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings


def get_embeddings_client():
    """Get the Google Generative AI embeddings client."""
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY not configured")
    
    return GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embedding_model,
        google_api_key=settings.google_api_key,
    )


@retry(
    retry=retry_if_exception_type(Exception),  # Catch generic Exception for 429s as langchain might wrap it
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5)
)
async def get_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text.
    """
    print(f"DEBUG: Generating embedding for text (length: {len(text)})...")
    client = get_embeddings_client()
    embedding = await client.aembed_query(text)
    
    # Handle dimensionality mismatch (Truncate if using 3072 model but DB expects 768)
    if len(embedding) == 3072 and settings.embedding_dimension == 768:
        print(f"DEBUG: Truncating 3072-dim to 768-dim (as requested by settings)")
        embedding = embedding[:768]
    
    print(f"DEBUG: Final embedding size: {len(embedding)}")
    return embedding


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5)
)
async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts.
    
    Batches requests for efficiency.
    """
    if not texts:
        return []
    
    client = get_embeddings_client()
    
    # Gemini free tier has rate limits, but aembed_documents handles some batching.
    # We still retry on failures.
    embeddings = await client.aembed_documents(texts)
    return embeddings


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    """
    import math
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)
