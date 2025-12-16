from typing import Dict, List
from Utils import CosignSimilarity
from ObjectInterfaces.LLM_Object import LLM_Object

import numpy as np


class EmbeddingVectorDocumentGenerator:
  def __init__(self, llmObject: LLM_Object, typesenseObject):
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
      similarity = CosignSimilarity.MultiVector(valueVector, biasVector)

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

  # ---- Helper functions ----

  def _normalize(self, value: float, min_val: float, max_val: float) -> float:
    # Map 0–1 similarity to custom range
    value = np.clip(value, 0.0, 1.0)  # safely clamp arrays or scalars
    return min_val + (max_val - min_val) * value

  def _normalize_vector(self, vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec
