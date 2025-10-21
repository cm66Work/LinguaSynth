from dataclasses import dataclass
import json
from typing import cast, List
import numpy as np
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import (
  EmbeddingVectorDocumentGenerator,
  LLM_Object,
)
from ObjectInterfaces.PostgresObject import Postgres_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject

# Convert the document quote to a vector embedding that is weighted towards the topic.
# Convert the schema fields to a vector embedding that is weighted towards the schema name.
# Find the closest matches schema to the document.
# Generate a document schema using the closes matching collection schema.
# Remove low confidence fields from the document schema
# index the document into typesense.


@dataclass
class QuoteSchemaRelationObject:
  """
  This object is used to show how each quote, topic, and document is related to which collection schema.
  """

  DocumentName: str
  Quote: str
  Topic: str
  QuoteEmbedding: list[float]
  SchemaName: str
  CurrentSimilarity: float


async def IndexNewDocuments(
  serverResponse: ServerResponse,
  typesenseObject: Typesense_Object,
  minioObject: MinIO_Object,
  llmObject: LLM_Object,
):
  """
  Indexes new documents from MinIO to the given Typesense schema.
  """
  # Initialize response
  response = serverResponse.GenerateServerResponse(ServerResponseObject())
  total_docs = minioObject.GetNumberOfObjectsInBucket('baseflow-summarized')

  response.Data = {'total_documents': total_docs, 'indexed_documents': 0}
  response.Message = 'Starting document indexing...'
  yield serverResponse.GenerateServerResponse(response)

  documentGenerator = EmbeddingVectorDocumentGenerator(
    llmObject, typesenseObject
  )
  quote_relations: List[QuoteSchemaRelationObject] = []

  # Iterate through documents
  for obj in minioObject.GetObjectsInBucket('baseflow-summarized'):
    response.Message = 'Indexing documents...'
    response.Data['indexed_documents'] += 1
    yield serverResponse.GenerateServerResponse(response)

    if not obj.object_name:
      continue

    # --- Step 1: Load and parse JSON content ---
    try:
      raw_content = minioObject.GetContentOfBucketObject(
        obj.bucket_name, obj.object_name
      ).Data['content']
      document_data = json.loads(raw_content)
    except Exception as e:
      print(f'Failed to parse JSON for {obj.object_name}: {e}')
      response.Message = (
        'Failed to parse document. Ensure all summaries are valid JSON.'
      )
      response.Success = False
      response.Finished = True
      yield serverResponse.GenerateServerResponse(response)
      return

    # --- Step 2: Generate quote/topic embeddings ---
    topics = [item['topic'] for item in document_data]
    quotes = [item['quote'] for item in document_data]
    embeddings = await documentGenerator.GenerateWeightedVectorEmbeddings(
      quotes, topics
    )

    for emb in embeddings:
      quote_relations.append(
        QuoteSchemaRelationObject(
          Topic=cast(str, emb['bias']),
          Quote=cast(str, emb['value']),
          QuoteEmbedding=cast(list[float], emb['embedding']),
          DocumentName=obj.object_name,
          SchemaName='',
          CurrentSimilarity=-9999,
        )
      )

    # --- Step 3: Generate schema embeddings ---
    response.Message = 'Generating schema vectors...'
    yield serverResponse.GenerateServerResponse(response)

    for schema in typesenseObject.GetAllSchemas():
      field_names = [field['name'] for field in schema['fields']]  # type: ignore
      schema_names = [schema['name']] * len(field_names)

      schema_embeddings = (
        await documentGenerator.GenerateWeightedVectorEmbeddings(
          field_names, schema_names
        )
      )
      schema_vectors = [
        cast(List[float], vec['embedding']) for vec in schema_embeddings
      ]

      combined_schema_vector = np.array(
        documentGenerator.CombineEmbeddings(schema_vectors)
      )

      # --- Step 4: Match quotes to schema using cosine similarity ---
      for relation in quote_relations:
        quote_vec = np.array(relation.QuoteEmbedding)
        similarity = documentGenerator.CosineSimilarity(
          quote_vec, combined_schema_vector
        )

        if similarity > relation.CurrentSimilarity:
          relation.CurrentSimilarity = similarity
          relation.SchemaName = schema['name']
