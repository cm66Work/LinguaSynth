import json
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from APIs.Schema.SchemaSimilarityCalculator import SchemaSimilarityCalculator
from Utils.ServerResponse import ServerResponse, ServerResponseObject
import numpy as np
from typing import List, Dict


async def UserQuery(
  serverResponse: ServerResponse,
  llmObject: LLM_Object,
  typesenseObject: Typesense_Object,
  userQuery: str,
  minioObject: MinIO_Object,
):
  """
  Generates embeddings for both the user query and the Typesense documents
  (dynamically, not stored), and returns the top 5 most semantically similar documents.
  """

  currentResponse = ServerResponseObject()
  currentResponse.Message = 'Processing schema similarity scores...'
  currentResponse.Data = {'answer': '', 'reference_document': ''}
  yield serverResponse.GenerateServerResponse(currentResponse)
  schemaSimilarityCalculator = SchemaSimilarityCalculator(
    llmObject, typesenseObject
  )
  try:
    result = await schemaSimilarityCalculator.GetSchemaSimilarityScores(
      userQuery
    )
    currentResponse.Message = 'Calculation Complete.'
    yield serverResponse.GenerateServerResponse(currentResponse)
    currentResponse.Message = 'Generating typesense Query.'
    yield serverResponse.GenerateServerResponse(currentResponse)
    typesenseQuery = typesenseObject.BuildUniversalTypesenseQuery(
      userQuery, str(result[0]['schema'])
    )
    print(typesenseQuery)

    currentResponse.Message = 'Query generated.'
    yield serverResponse.GenerateServerResponse(currentResponse)
    currentResponse.Message = 'Querying Typesense.'
    yield serverResponse.GenerateServerResponse(currentResponse)
    queryResult = typesenseObject.Query(
      str(result[0]['schema']), json.dumps(typesenseQuery)
    )
    topHitDocument = queryResult.Data['result']['hits']
    currentResponse.Data['reference_document'] = GetDocumentsFromQueryHits(
      topHitDocument
    )

    document = minioObject.GetContentOfBucketObject(
      'testing-processed', currentResponse.Data['reference_document'][0]
    )
    prompt = f"""{document}
      Using the above document answer the following user question: {userQuery}"""
    generatedResponse = await llmObject.Generate(prompt)
    currentResponse.Data['answer'] = generatedResponse.Response
    print(currentResponse)

  except ValueError as e:
    currentResponse.Success = False
    currentResponse.Finished = True
    currentResponse.Message = f'Value Error:: {e}'
    currentResponse.Data = {'answer': '', 'reference_document': ''}
    yield serverResponse.GenerateServerResponse(currentResponse)


def GetDocumentsFromQueryHits(hits):
  documentNames: list[str] = []
  for document in hits:
    if document['document']['document_name'] in documentNames:
      continue
    documentNames.append(document['document']['document_name'])
  return documentNames


async def GetEmbeddingsForContent(self, texts: List[str]) -> List[List[float]]:
  """
  Uses Ollama embeddinggemma:300m via llmObject client to get embeddings.
  """
  return await self.llmObject.client.GetEmbeddings(texts, 'embeddinggemma:300m')


async def GetSchemaSimilarityScores(
  self, schema_names: List[str], user_query: str
) -> List[Dict[str, float]]:
  """
  Takes a list of Typesense schema names and a user query string.
  Uses Ollama embeddings and cosine similarity to compute a similarity percentage
  for each schema relative to the query.
  """

  if not schema_names:
    return []
  if not user_query or not isinstance(user_query, str):
    raise ValueError('user_query must be a non-empty string.')

  # Clean and deduplicate schema names
  seen = set()
  cleaned = []
  for name in schema_names:
    if name and name.strip() and name not in seen:
      cleaned.append(name)
      seen.add(name)

  if not cleaned:
    return []

  # Combine all texts for one batch embedding call
  texts = [user_query] + cleaned
  embeddings = await self.GetEmbeddingsForContent(texts)

  if not embeddings or len(embeddings) != len(texts):
    raise RuntimeError(
      'Embedding generation failed or returned unexpected results.'
    )

  # Extract query and schema embeddings
  query_vec = np.array(embeddings[0], dtype=float)
  schema_vecs = np.array(embeddings[1:], dtype=float)

  # Normalize all vectors to unit length
  query_norm = np.linalg.norm(query_vec)
  schema_norms = np.linalg.norm(schema_vecs, axis=1)
  if query_norm == 0 or np.any(schema_norms == 0):
    raise ValueError('Encountered zero-length embedding vector(s).')

  normalized_query = query_vec / query_norm
  normalized_schema_vecs = schema_vecs / schema_norms[:, np.newaxis]

  # Compute cosine similarity (dot product of normalized vectors)
  cosine_similarities = np.dot(normalized_schema_vecs, normalized_query)

  # Convert similarity to percentage
  similarity_percentages = np.clip(cosine_similarities, -1.0, 1.0) * 100.0

  # Prepare structured output
  results = [
    {'schema': name, 'similarity_pct': round(float(score), 2)}
    for name, score in zip(cleaned, similarity_percentages)
  ]

  # Sort descending by similarity
  results.sort(key=lambda x: x['similarity_pct'], reverse=True)

  return results
