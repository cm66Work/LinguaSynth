from dataclasses import dataclass
from typing import List, Tuple
from ObjectInterfaces.LLM_Object import LLM_Object
import numpy as np


@dataclass
class QuoteObject:
  Quote: str
  Topic: str
  ClosestMatchingSchemaName: str


class SchemaMatcher:
  """
  Uses your existing Ollama-based embedding endpoint to select the best Typesense schema
  for a QuoteObject's Topic via cosine similarity.
  """

  def __init__(self, llmObject: LLM_Object):
    self.llmObject: LLM_Object = llmObject

  @staticmethod
  def _flatten_embedding(e) -> np.ndarray:
    """
    Convert shapes like (1,1,768) or (1,768) to strict (768,) vectors.
    """
    arr = np.asarray(e, dtype=float)
    arr = np.squeeze(arr)
    if arr.ndim != 1:
      arr = arr.reshape(-1)
    return arr

  async def GetEmbeddingsForContent(
    self, texts: List[str]
  ) -> List[List[float]]:
    """
    Uses Ollama embeddinggemma:300m via llmObject client to get embeddings.
    """
    return await self.llmObject.client.GetEmbeddings(
      texts, 'embeddinggemma:300m'
    )

  async def GetBestSchemaForQuoteTopic(
    self, quote: QuoteObject, schema_names: List[str], return_score: bool = True
  ) -> Tuple[str, float] | str:
    """
    Given a QuoteObject and a list of Typesense collection schema names, embed the Topic
    and all schema names, compute cosine similarity, and return the best-matching schema.
    Optionally returns the similarity percentage alongside the name.
    """

    if not isinstance(quote, QuoteObject):
      raise ValueError('quote must be an instance of QuoteObject.')
    if not isinstance(quote.Topic, str) or not quote.Topic.strip():
      raise ValueError('QuoteObject.Topic must be a non-empty string.')
    if not schema_names:
      raise ValueError('schema_names must be a non-empty list of schema names.')

    # Clean and de-duplicate schema names while preserving order
    seen = set()
    cleaned: List[str] = []
    for s in schema_names:
      if isinstance(s, str) and s.strip() and s not in seen:
        cleaned.append(s)
        seen.add(s)
    if not cleaned:
      raise ValueError('No valid schema names after cleaning input.')

    # Batch-embed the topic + schemas
    texts = [quote.Topic] + cleaned
    raw_embeddings = await self.GetEmbeddingsForContent(texts)
    if not raw_embeddings or len(raw_embeddings) != len(texts):
      raise RuntimeError(
        'Embedding generation failed or returned unexpected length.'
      )

    topic_vec = self._flatten_embedding(raw_embeddings[0])
    schema_vecs = np.stack(
      [self._flatten_embedding(e) for e in raw_embeddings[1:]], axis=0
    )

    if topic_vec.ndim != 1 or schema_vecs.ndim != 2:
      raise ValueError(
        f'Unexpected embedding shapes: topic {topic_vec.shape}, schemas {schema_vecs.shape}.'
      )
    if schema_vecs.shape[1] != topic_vec.shape[0]:
      raise ValueError(
        f'Feature dimension mismatch between topic {topic_vec.shape} and schemas {schema_vecs.shape}.'
      )

    # Normalize and compute cosine similarity
    t_norm = np.linalg.norm(topic_vec)
    s_norms = np.linalg.norm(schema_vecs, axis=1)
    if t_norm == 0 or np.any(s_norms == 0):
      raise ValueError('Encountered zero-length embedding vector(s).')

    topic_unit = topic_vec / t_norm
    schemas_unit = schema_vecs / s_norms[:, None]
    sims = schemas_unit @ topic_unit  # cosine similarity

    # Identify best schema
    best_idx = int(np.argmax(sims))
    best_schema = cleaned[best_idx]
    best_pct = float(np.clip(sims[best_idx], -1.0, 1.0) * 100.0)

    # Optionally update the QuoteObject in-place with the winner
    quote.ClosestMatchingSchemaName = best_schema

    return (best_schema, round(best_pct, 2)) if return_score else best_schema


# -----------------------------
# Example usage
# -----------------------------
# matcher = SchemaMatcher(llmObject)
# q = QuoteObject(
#     Quote="Our consultants are experts in their field...",
#     Topic="Consultant Expertise",
#     ClosestMatchingSchemaName=""
# )
# winner, score = await matcher.GetBestSchemaForQuoteTopic(
#     q, ["consulting_quotes", "project_success", "customer_stories"]
# )
# print(winner, score)  # e.g., "consulting_quotes", 86.42
