import json
from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.LLM_Object import LLM_Object, SchemaSimilarityCalculator
from Utils.ServerResponse import ServerResponse, ServerResponseObject
import numpy as np
from typing import List, Dict


async def UserQuery(
  serverResponse: ServerResponse,
  llmObject: LLM_Object,
  typesenseObject: Typesense_Object,
  userQuery: str,
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
    print(result[0]['schema'])
  except ValueError as e:
    currentResponse.Success = False
    currentResponse.Finished = True
    currentResponse.Message = f'Value Error:: {e}'
    currentResponse.Data = {'answer': '', 'reference_document': ''}
    yield serverResponse.GenerateServerResponse(currentResponse)

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
  print(queryResult.Data['result']['hits'][0]['document'])
  return

  # Get all ;typesense schemas and  convert teach one into a vector embedding.
  # Compare the users query to see which  schema matches it the . closest

  # Step 1: Get the embedding for the user query
  # Flatten query embedding
  query_embedding = np.array(
    (await llmObject.GetEmbeddingsForContent([userQuery]))[0], dtype=np.float32
  )
  # removes (1,1,768) -> (768,)
  query_embedding = np.squeeze(query_embedding)

  # Step 2: Retrieve all schemas
  schemas = typesenseObject.GetAllSchemas()
  all_docs = []

  # Step 3: Extract documents from each schema
  for schema in schemas:
    try:
      # Get documents (depending on your Typesense setup)
      typesenseResponse = typesenseObject.DocumentSearch(schema['name'])
      docs = typesenseResponse.Data['documents']
      hits = docs.get('hits', [])
      for hit in hits:
        doc = hit.get('document', {})
        text = None

        # Attempt to find a suitable text field
        for key in ['content', 'text', 'body', 'description', 'title']:
          if key in doc and isinstance(doc[key], str):
            text = doc[key]
            break

        if text:
          all_docs.append(
            {'collection': schema['name'], 'id': doc.get('id'), 'text': text}
          )
    except Exception as e:
      print(f'Error loading documents from {schema["name"]}: {e}')

  if not all_docs:
    serverResponse.status = 'no_documents'
    serverResponse.results = []
    yield serverResponse
    return

  # Step 4: Generate embeddings for all document texts
  texts = [doc['text'] for doc in all_docs]
  doc_embeddings_raw = await llmObject.GetEmbeddingsForContent(texts)
  doc_embeddings = np.array(
    [np.squeeze(e) for e in doc_embeddings_raw], dtype=np.float32
  )

  # Step 5: Compute cosine similarity
  query_norm = query_embedding / np.linalg.norm(query_embedding)
  doc_norms = doc_embeddings / np.linalg.norm(
    doc_embeddings, axis=1, keepdims=True
  )
  similarities = np.dot(doc_norms, query_norm)

  # Step 6: Rank and select top 5
  top_indices = np.argsort(similarities)[::-1][:5]
  top_docs = [
    {
      'collection': all_docs[i]['collection'],
      'id': all_docs[i]['id'],
      'text': all_docs[i]['text'],
      'similarity': float(similarities[i]),
    }
    for i in top_indices
  ]

  # Step 7: Return the response
  serverResponse.results = top_docs
  serverResponse.status = 'success' if top_docs else 'no_results'
  yield serverResponse
  return


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
