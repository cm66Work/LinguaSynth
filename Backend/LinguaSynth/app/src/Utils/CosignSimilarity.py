import numpy as np


def MultiVector(a: np.ndarray, b: np.ndarray) -> float:
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


def SingleVector(v1, v2) -> float:
  a = np.asarray(v1, dtype=float).ravel()
  b = np.asarray(v2, dtype=float).ravel()

  denom = np.linalg.norm(a) * np.linalg.norm(b)
  if denom == 0.0:
    return 0.0

  return float(np.dot(a, b) / denom)
