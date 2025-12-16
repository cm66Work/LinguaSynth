import numpy as np
from typing import List, Dict, Any, Optional


class SemanticFieldMatcher:
  def __init__(self, llmObject):
    self.llmObject = llmObject

  @staticmethod
  def _flatten_embedding(e) -> np.ndarray:
    arr = np.asarray(e, dtype=float)
    arr = np.squeeze(arr)
    if arr.ndim != 1:
      arr = arr.reshape(-1)
    return arr

  @staticmethod
  def _normalize_matrix(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    if np.any(norms == 0):
      raise ValueError('Encountered zero-length embedding vector(s).')
    return m / norms

  async def GetEmbeddingsForContent(
    self, texts: List[str]
  ) -> List[List[float]]:
    """
    Uses Ollama embeddinggemma:300m via llmObject client to get embeddings.
    """
    return await self.llmObject.client.GetEmbeddings(
      texts, 'embeddinggemma:300m'
    )

  async def MatchTopicsToSchemaFields(
    self,
    topics: List[Dict[str, str]],
    schema: Dict[str, Any],
    threshold: float = 0.6,
    field_text_transform: Optional[str] = None,
  ) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Inputs
      topics: list of {'topic': 'topic name', 'quote': 'optional evidence'}.
              Only 'topic' participates in similarity.
      schema: a Typesense collection schema dict with 'fields' entries.
      threshold: cosine similarity in [0, 1]; values below this remain unmatched.
      field_text_transform: optional mode to enrich field labels. Supported: None or 'humanize'.

    Output
      {'fields': { '<field_name>': '<matched topic>' or None }}
    """

    if not isinstance(topics, list) or len(topics) == 0:
      raise ValueError('Provide at least one topic object.')
    if (
      not isinstance(schema, dict)
      or 'fields' not in schema
      or not schema['fields']
    ):
      raise ValueError("Schema must include a non-empty 'fields' array.")
    if not (0.0 <= float(threshold) <= 1.0):
      raise ValueError('Threshold must be a float in [0, 1].')

    # Prepare topic texts and field labels
    topic_texts = []
    topic_keys = []
    for obj in topics:
      t = (obj.get('topic') or '').strip()
      if t:
        topic_texts.append(t)
        topic_keys.append(t)
    if not topic_texts:
      raise ValueError("No valid non-empty 'topic' strings were found.")

    def _humanize(name: str) -> str:
      # simple readability pass for embedding quality
      n = name.replace('_', ' ')
      return n

    field_entries = schema['fields']
    field_names = []
    field_texts = []
    for f in field_entries:
      name = str(f.get('name', '')).strip()
      if not name:
        continue
      field_names.append(name)
      if field_text_transform == 'humanize':
        field_texts.append(_humanize(name))
      else:
        field_texts.append(name)

    if not field_names:
      raise ValueError('No valid field names found in schema.')

    # Batch embed: topics then fields
    texts = topic_texts + field_texts
    raw_embeddings = await self.GetEmbeddingsForContent(texts)
    if not raw_embeddings or len(raw_embeddings) != len(texts):
      raise RuntimeError(
        'Embedding generation failed or returned unexpected results.'
      )

    topic_vecs = np.stack(
      [self._flatten_embedding(e) for e in raw_embeddings[: len(topic_texts)]],
      axis=0,
    )
    field_vecs = np.stack(
      [self._flatten_embedding(e) for e in raw_embeddings[len(topic_texts) :]],
      axis=0,
    )

    # Normalize to unit length for cosine similarity
    topic_vecs = self._normalize_matrix(topic_vecs)
    field_vecs = self._normalize_matrix(field_vecs)

    # Similarity matrix: fields x topics
    sims = field_vecs @ topic_vecs.T  # cosine since normalized

    # Greedy one-to-field assignment: best topic per field subject to threshold
    mapping: Dict[str, Optional[str]] = {}
    for i, fname in enumerate(field_names):
      row = sims[i]
      best_idx = int(np.argmax(row))
      best_sim = float(row[best_idx])
      if best_sim >= threshold:
        mapping[fname] = topic_keys[best_idx]
      else:
        mapping[fname] = None

    return {'fields': mapping}
