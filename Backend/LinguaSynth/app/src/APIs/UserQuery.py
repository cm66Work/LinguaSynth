from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject
import numpy as np


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
  currentResponse.Success = True
  currentResponse.Finished = True
  currentResponse.Message = 'Generating response...'
  currentResponse.Data = {'answer': '', 'reference_document': ''}
  yield serverResponse.GenerateServerResponse(currentResponse)
  return

  # Step 1: Get the embedding for the user query
  # Flatten query embedding
  query_embedding = np.array(
    (await llmObject.GetEmbeddingsForContent([userQuery]))[0], dtype=np.float32
  )
  query_embedding = np.squeeze(query_embedding)  # removes (1,1,768) -> (768,)

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
