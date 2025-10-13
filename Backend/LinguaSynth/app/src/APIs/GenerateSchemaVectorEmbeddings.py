import re
import numpy as np
from sklearn.cluster import KMeans


from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from Utils.ServerResponse import ServerResponse


async def SchemaGenerationVectorEmbeddings(
  bucketRootName: str,
  sampleSize: int,
  serverResponse: ServerResponse,
  minioObject: MinIO_Object,
  llmObject: LLM_Object,
  resolution: int = 1,
  force: bool = False,
  tagCompression: float = 0.25,
):
  bucketName = f'{bucketRootName}-summarized'
  combinedDocument = ''
  for document in minioObject.GetObjectsInBucket(bucketName):
    combinedDocument += (
      minioObject.GetContentOfBucketObject(
        bucketName,
        document.object_name,  # type: ignore
      ).Data['content']
      + '\n'
    )
  print(combinedDocument)

  result = await infer_schema_from_doc(combinedDocument, llmObject, 15)
  print(result)


def cosine_sim(a, b):
  a, b = np.array(a).squeeze(), np.array(b).squeeze()
  return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


async def infer_schema_from_doc(text: str, llmObject: LLM_Object, n_clusters: int = 5):
  """
  Infer a Typesense schema structure from an unstructured document.
  Uses Ollama embeddings and KMeans clustering to propose field names.
  """
  # --- Step 1: chunk text ---
  chunks = [p.strip() for p in re.split(r'\n{1,}|\. ', text) if len(p.strip()) > 20]

  # --- Step 2: get embeddings ---
  embeddings = await llmObject.GetEmbeddingsForContent(chunks)
  embeddings = np.array([np.array(e).squeeze() for e in embeddings if len(e)])

  # --- Step 3: cluster embeddings ---
  n_clusters = min(n_clusters, len(embeddings))
  kmeans = KMeans(n_clusters=n_clusters, n_init='auto').fit(embeddings)
  labels = kmeans.labels_

  # --- Step 4: pick representative sentences for each cluster ---
  schema_fields = []
  for cluster_id in range(n_clusters):
    cluster_indices = np.where(labels == cluster_id)[0]
    if not len(cluster_indices):
      continue
    representative_idx = cluster_indices[0]
    candidate_text = chunks[representative_idx]

    # Very simple noun-phrase heuristic for field name
    words = [w for w in re.findall(r'[A-Za-z]{3,}', candidate_text)]
    top_words = [w.lower() for w in words[:3]]
    name = '_'.join(top_words[:2]) if top_words else f'field_{cluster_id}'

    schema_fields.append({'name': name[:40], 'type': 'string'})

  # --- Step 5: merge duplicates / clean names ---
  seen = set()
  unique_fields = []
  for f in schema_fields:
    if f['name'] not in seen:
      unique_fields.append(f)
      seen.add(f['name'])

  return {'fields': unique_fields}
