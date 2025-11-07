import json
import os
import re
from typing import Dict, List, cast
from Managers.LLMManager import LLMManager, LLMServerResponseObject
from ObjectInterfaces.Typesense_Object import Typesense_Object
from typesense.types.collection import (
  CollectionSchema,
  CollectionCreateSchema,
  RegularCollectionFieldSchema,
  ReferenceCollectionFieldSchema,
)
import numpy as np
# from jsonschema import validate, ValidationError

# --- Constants ---
LLM_LIGHT_GENERATION_MODEL = 'gemma3:1b'
LLM_HEAVY_GENERATION_MODEL = 'gemma3:12b'
LLM_EMBEDDING_MODEL = 'embeddinggemma:300m'
SCHEMA_FIELDS_FORMAT = {
  'fields': {
    'company_name': {'type': 'string'},
    'year_created': {'type': 'integer'},
  }
}
LLM_SCHEMA_FILE_NAME = 'schema.txt'


class LLM_Object:
  def __init__(self):
    address = os.getenv('OLLAMA_ADDRESS', 'ollama')
    port = os.getenv('OLLAMA_PORT', '11434')
    self.client = LLMManager(hostAddress=f'{address}:{port}')

  # --- Handlers ---
  async def Generate(self, prompt: str, format={}) -> LLMServerResponseObject:
    return await self.client.Generate(
      model=LLM_LIGHT_GENERATION_MODEL, prompt=prompt, format=format
    )


class EmbeddingVectorSchemaGenerator:
  def __init__(self, llmObject: LLM_Object, typesenseObject: Typesense_Object):
    self.llmObject: LLM_Object = llmObject
    self.typesenseObject: Typesense_Object = typesenseObject

  async def ReprocessSchema(
    self,
    currentSchema,
    document,
    confidenceThreshold: float = 0.01,
  ) -> CollectionSchema:
    try:
      currentSchema = cast(CollectionSchema, currentSchema)
      document = json.loads(document)
    except Exception:
      return currentSchema

    # candidate_fields = self.extract_field_candidates(document)
    candidate_fields = [entry['topic'] for entry in document]
    # pass this lower
    existing_field_names = [f['name'] for f in currentSchema['fields']]  # type: ignore

    all_texts = existing_field_names + candidate_fields
    if not all_texts:
      return currentSchema

    # check and remove similar fields from the schema.
    all_embeddings = await self.GetEmbeddingsForContent(all_texts)
    existing_embeds = all_embeddings[: len(existing_field_names)]
    candidate_embeds = all_embeddings[len(existing_field_names) :]

    refinedFields = list(currentSchema['fields'])

    for i, cand_embed in enumerate(candidate_embeds):
      cand_name = candidate_fields[i]

      if len(existing_embeds) > 0:
        similarities = self.cosine_similarity_np([cand_embed], existing_embeds)[
          0
        ]
        max_sim = float(np.max(similarities))
      else:
        max_sim = 0.0

      # remove the fields with low confidence thresholds
      if round(1 - max_sim, 3) < confidenceThreshold:
        continue  # field confidence is too low and its ignored.
      refinedFields.append(
        {
          'name': cand_name.lower().replace(' ', '_'),
          'type': 'string',
        }
      )
    refinedFields = await self.deduplicate_fields(refinedFields)
    currentSchema['fields'] = cast(
      list[RegularCollectionFieldSchema | ReferenceCollectionFieldSchema],
      refinedFields,
    )
    currentSchema['name'] = (
      await self.llmObject.Generate(
        f'Give the following json object a new or phrase which represents and outlines the information in the json object.\nJsonObject: {refinedFields}\n Answer only with the name limited to 10 words.'
      )
    ).Response

    def FilterName(schemaName: str) -> str:
      filterList = [':', ',', '.', '*', '\n', '/']
      for filter in filterList:
        schemaName = schemaName.replace(filter, '')
      schemaName = schemaName.replace(' ', '_')
      schemaName = schemaName.lower()
      return schemaName

    currentSchema['name'] = FilterName(currentSchema['name'])
    return currentSchema

  async def GetEmbeddingsForContent(
    self, texts: List[str]
  ) -> List[List[float]]:
    return await self.llmObject.client.GetEmbeddings(texts, LLM_EMBEDDING_MODEL)

  def cosine_similarity_np(self, a, b):
    """Same fixed version as before."""
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    if a.ndim > 2:
      a = a.reshape(a.shape[0], -1)
    if b.ndim > 2:
      b = b.reshape(b.shape[0], -1)
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return np.dot(a_norm, b_norm.T)

  async def deduplicate_fields(
    self, fields, threshold=0.96
  ) -> list[RegularCollectionFieldSchema | ReferenceCollectionFieldSchema]:
    names = [f['name'] for f in fields]
    embeddings = await self.GetEmbeddingsForContent(names)
    sim_matrix = self.cosine_similarity_np(embeddings, embeddings)

    keep = []
    removed = set()
    for i, name in enumerate(names):
      if name in removed:
        continue
      for j in range(i + 1, len(names)):
        if sim_matrix[i][j] > threshold:
          removed.add(names[j])
      keep.append(fields[i])
    return [f for f in keep if f['name'] not in removed]

  async def InferFieldType(
    self,
    field_name: str,
    field_context: str,
    llmObject,
    numberConfidenceThreshold: float = 0.85,
  ) -> str:
    """
    Infers whether a field should be a 'number' or 'string' based on its content and semantics.
    Uses regex heuristics and semantic similarity via embeddings.
    """

    # --- Step 1: Heuristic check for numeric pattern ---
    if re.fullmatch(
      r'[-+]?[0-9]*[.,]?[0-9]+(?:[eE][-+]?[0-9]+)?[%$kKmMbB]*',
      field_context.strip(),
    ):
      return 'number'

    # --- Step 2: Prepare embeddings for semantic similarity ---
    reference_terms = [
      'number',
      'numeric',
      'amount',
      'quantity',
      'value',
      'count',
    ]
    comparison_texts = [field_name] + reference_terms
    embeddings = await llmObject.GetEmbeddingsForContent(comparison_texts)

    field_embed = np.array(embeddings[0])
    ref_embeds = np.array(embeddings[1:])
    field_embed = field_embed.reshape(1, -1)
    ref_embeds = ref_embeds / np.linalg.norm(ref_embeds, axis=1, keepdims=True)
    field_embed = field_embed / np.linalg.norm(
      field_embed, axis=1, keepdims=True
    )
    sims = np.dot(field_embed, ref_embeds.T)[0]

    # --- Step 3: Threshold-based semantic decision ---
    if np.max(sims) > numberConfidenceThreshold:
      return 'number'
    return 'string'


class EmbeddingVectorDocumentGenerator:
  def __init__(self, llmObject, typesenseObject):
    self.llmObject = llmObject
    self.typesenseObject = typesenseObject

  async def GetEmbeddingsForContent(
    self, texts: List[str]
  ) -> List[List[float]]:
    """
    Uses Ollama embeddinggemma:300m via llmObject client to get embeddings.
    """
    return await self.llmObject.client.GetEmbeddings(
      texts, 'embeddinggemma:300m'
    )

  async def GenerateWeightedVectorEmbeddings(
    self, values: List[str], biases: List[str]
  ) -> List[Dict[str, object]]:
    """
    Generates weighted embeddings vectors from values that are grouped around the bias
    """

    # Step 1: Get embeddings from LLM (parallel)
    valueVectors = await self.GetEmbeddingsForContent(values)
    biasesVectors = await self.GetEmbeddingsForContent(biases)

    # Convert to numpy arrays for easier math
    valueVectors = [np.array(v) for v in valueVectors]
    biasesVectors = [np.array(v) for v in biasesVectors]

    results = []
    for i, item in enumerate(values):
      valueVector = valueVectors[i]
      biasVector = biasesVectors[i]

      # Step 2: Compute cosine similarity between topic and quote
      similarity = self.CosineSimilarity(valueVector, biasVector)

      # Step 3: Compute topic weight (normalized between 0.3 and 0.8)
      weight = self._normalize(similarity, min_val=0.3, max_val=0.8)

      # Step 4: Combine embeddings
      weighted_vec = self._normalize_vector(
        weight * valueVector + (1 - weight) * biasVector
      )

      results.append(
        {
          'value': values[i],
          'bias': biases[i],
          'embedding': weighted_vec.tolist(),
        }
      )

    return results

  def CombineEmbeddings(self, vectors: List[List[float]]) -> List[float]:
    """
    Combines a list of embedding vectors into a single representative vector.
    Method: computes the mean vector (centroid) and normalizes it.

    Args:
        vectors (List[List[float]]): List of embedding vectors (same dimensionality)

    Returns:
        List[float]: Single normalized combined embedding vector
    """
    if not vectors:
      raise ValueError('No vectors provided for combination.')

    # Convert all to numpy arrays
    np_vectors = [np.array(v) for v in vectors]

    # Step 1: Compute mean vector (element-wise average)
    mean_vec = np.mean(np.stack(np_vectors), axis=0)

    # Step 2: Normalize the combined vector
    normalized_vec = self._normalize_vector(mean_vec)

    return normalized_vec.tolist()

  # ---- Helper functions ----

  def CosineSimilarity(self, a: np.ndarray, b: np.ndarray) -> float:
    """Returns how close a is to b, eg how similar a is to b."""
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    if a.ndim > 2:
      a = a.reshape(a.shape[0], -1)
    if b.ndim > 2:
      b = b.reshape(b.shape[0], -1)
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return np.dot(a_norm, b_norm.T)

  def _normalize(self, value: float, min_val: float, max_val: float) -> float:
    # Map 0–1 similarity to custom range
    value = np.clip(value, 0.0, 1.0)  # safely clamp arrays or scalars
    return min_val + (max_val - min_val) * value

  def _normalize_vector(self, vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


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
