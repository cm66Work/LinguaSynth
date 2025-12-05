from typing import Dict, List
from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from typesense.types.collection import (
  CollectionSchema,
)
import numpy as np


class SchemaSimilarityCalculator:
  def __init__(self, llmObject: LLM_Object, typesenseObject: Typesense_Object):
    self.llmObject = llmObject
    self.typesenseObject = typesenseObject

  async def __GetEmbeddingsForContent(
    self, texts: List[str]
  ) -> List[List[float]]:
    """
    Uses Ollama embeddinggemma:300m via llmObject client to get embeddings.
    """
    return await self.llmObject.client.GetEmbeddings(
      texts, 'embeddinggemma:300m'
    )

  @staticmethod
  def _flatten_embedding(e) -> np.ndarray:
    """
    Converts any nested embedding like (1,1,768), (1,768), or [[...]] to a clean 1D array (768,).
    """
    arr = np.asarray(e, dtype=float)
    arr = np.squeeze(arr)
    if arr.ndim != 1:
      # As a last resort, collapse to 1D while preserving the feature dimension
      arr = arr.reshape(-1)
    return arr

  async def GetSchemaSimilarityScores(
    self, user_query: str
  ) -> List[Dict[str, float]]:
    """
    Takes a list of Typesense schema names and a user query string.
    Uses Ollama embeddings and cosine similarity to compute a similarity percentage
    for each schema relative to the query.
    """

    schemas: list[CollectionSchema] = self.typesenseObject.GetAllSchemas()
    schemaNames = [schema['name'] for schema in schemas]
    if not schemaNames:
      return []
    if not isinstance(user_query, str) or not user_query.strip():
      raise ValueError('user_query must be a non-empty string.')

    seen = set()
    cleaned = []
    for name in schemaNames:
      if name and name.strip() and name not in seen:
        cleaned.append(name)
        seen.add(name)
    if not cleaned:
      return []

    texts = [user_query] + cleaned
    rawEmbeddings = await self.__GetEmbeddingsForContent(texts)

    if not rawEmbeddings or len(rawEmbeddings) != len(texts):
      raise RuntimeError(
        'Embedding generation failed or returned unexpected results.'
      )

    query_vec = self._flatten_embedding(rawEmbeddings[0])
    schema_vecs = np.stack(
      [self._flatten_embedding(e) for e in rawEmbeddings[1:]], axis=0
    )

    if query_vec.ndim != 1:
      raise ValueError(
        f'Query embedding must be 1D after flattening, got shape {query_vec.shape}.'
      )
    if schema_vecs.ndim != 2:
      raise ValueError(
        f'Schema embeddings must be 2D after stacking, got shape {schema_vecs.shape}.'
      )
    if schema_vecs.shape[1] != query_vec.shape[0]:
      raise ValueError(
        f'Feature dimension mismatch between schemas {schema_vecs.shape} and query {query_vec.shape}.'
      )

    qn = np.linalg.norm(query_vec)
    sn = np.linalg.norm(schema_vecs, axis=1)
    if qn == 0 or np.any(sn == 0):
      raise ValueError('Encountered zero-length embedding vector(s).')

    normalized_query = query_vec / qn
    normalized_schema_vecs = schema_vecs / sn[:, None]

    cosine_similarities = normalized_schema_vecs @ normalized_query
    similarity_percentages = np.clip(cosine_similarities, -1.0, 1.0) * 100.0

    results = [
      {'schema': name, 'similarity_pct': round(float(score), 2)}
      for name, score in zip(cleaned, similarity_percentages)
    ]
    results.sort(key=lambda x: x['similarity_pct'], reverse=True)
    return results
