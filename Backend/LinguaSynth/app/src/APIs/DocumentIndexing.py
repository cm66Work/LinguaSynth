from dataclasses import dataclass
import json
from typing import cast
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
  documentGenerator = EmbeddingVectorDocumentGenerator(
    llmObject, typesenseObject
  )
  currentResponse = serverResponse.GenerateServerResponse(
    ServerResponseObject()
  )
  currentResponse.Data = {
    'total_documents': minioObject.GetNumberOfObjectsInBucket(
      'baseflow-summarized'
    ),
    'indexed_documents': 0,
  }
  currentResponse.Message = 'Starting document indexing...'
  yield serverResponse.GenerateServerResponse(currentResponse)
  quoteSchemaRelationObjects: list[QuoteSchemaRelationObject] = []
  # Generate document vector embeddings.
  for bucketObject in minioObject.GetObjectsInBucket('baseflow-summarized'):
    currentResponse.Message = 'indexing documents...'
    currentResponse.Data['indexed_documents'] += 1
    yield serverResponse.GenerateServerResponse(currentResponse)
    if bucketObject.object_name is None:
      continue
    try:
      objectContent = json.loads(
        minioObject.GetContentOfBucketObject(
          bucketObject.bucket_name, bucketObject.object_name
        ).Data['content']
      )
    except Exception as e:
      print('failed to load json content', e)
      currentResponse.Message = 'Failed to parse document. Are all documents summarized in a json format?'
      currentResponse.Success = False
      currentResponse.Finished = True
      yield serverResponse.GenerateServerResponse(currentResponse)
      return

    # Extract topics and quotes
    topics = [item['topic'] for item in objectContent]
    quotes = [item['quote'] for item in objectContent]
    documentEmbeddings = (
      await documentGenerator.GenerateWeightedVectorEmbeddings(quotes, topics)
    )
    # Create default relation object.
    # Will be set later once we have embedded our schemas.
    for embeddingResult in documentEmbeddings:
      quoteSchemaRelationObjects.append(
        QuoteSchemaRelationObject(
          Topic=cast(str, embeddingResult['bias']),
          Quote=cast(str, embeddingResult['value']),
          QuoteEmbedding=cast(list[float], embeddingResult['embedding']),
          DocumentName=bucketObject.object_name,
          SchemaName='',
          CurrentSimilarity=-9999,
        )
      )

    # Generate schema vector embeddings.
    currentResponse.Message = 'Generating schema vectors'
    yield serverResponse.GenerateServerResponse(currentResponse)

    # schemaVectors: list[list[float]] = []
    # Extract schema names and field names
    collections = typesenseObject.GetAllSchemas()
    # Need duplicates of the schema names so that our vector embeddings shape remains the same between the field names and the schema names.
    schemaNames = []
    fieldNames = []
    for schema in collections:
      # Generate the values and the bias
      for field in schema['fields']:
        schemaNames.append(schema['name'])
        fieldNames.append(field['name'])  # type: ignore

      # Calculate the embeddings and collapse to single vector.
      schemaEmbeddings = (
        await documentGenerator.GenerateWeightedVectorEmbeddings(
          fieldNames, schemaNames
        )
      )
      schemaVectors = cast(
        list[list[float]], [vector['embedding'] for vector in schemaEmbeddings]
      )
      # schemaVectors.append(documentGenerator.CombineEmbeddings(schemaVectors))

      # We now have all schema vectors calculated.
      # Find out which schema is closest to every quote in this document.
      for i, item in enumerate(quoteSchemaRelationObjects):
        quoteEmbedding = np.array(quoteSchemaRelationObjects[i].QuoteEmbedding)
        combinedSchemaVector = np.array(
          documentGenerator.CombineEmbeddings(schemaVectors)
        )
        similarity = documentGenerator.CosineSimilarity(
          quoteEmbedding, combinedSchemaVector
        )
        if similarity > quoteSchemaRelationObjects[i].CurrentSimilarity:
          quoteSchemaRelationObjects[i].CurrentSimilarity = similarity
          quoteSchemaRelationObjects[i].SchemaName = schema['name']
