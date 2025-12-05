from dataclasses import dataclass
import json
from typing import cast, List, Dict, Any
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import (
  LLM_Object,
)
from typesense.types.document import DocumentSchema
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils.QuoteMatcher import QuoteObject, SchemaMatcher
from Utils.SemanticFieldMatcher import SemanticFieldMatcher


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


@dataclass
class Document:
  DocumentName: str
  QuoteSchemaRelations: List[QuoteSchemaRelationObject]

  def GetRelatedSchemas(self):
    uniqueSchemaNames: List[str] = []
    for quoteRelation in self.QuoteSchemaRelations:
      if quoteRelation.SchemaName not in uniqueSchemaNames:
        uniqueSchemaNames.append(quoteRelation.SchemaName)
    return uniqueSchemaNames


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
  totalDocs = minioObject.GetNumberOfObjectsInBucket('testing-summarized')

  response.Data = {'total_documents': totalDocs, 'indexed_documents': 0}
  response.Message = 'Starting document indexing...'
  yield serverResponse.GenerateServerResponse(response)

  response.Message = 'Fetching Typesense collections.'
  yield serverResponse.GenerateServerResponse(response)
  schemaNames = [schema['name'] for schema in typesenseObject.GetAllSchemas()]
  schemaMatcher = SchemaMatcher(llmObject)
  semanticFieldMatcher = SemanticFieldMatcher(llmObject)
  response.Message = 'Done.'
  yield serverResponse.GenerateServerResponse(response)

  response.Message = 'Indexing documents...'
  yield serverResponse.GenerateServerResponse(response)

  for obj in minioObject.GetObjectsInBucket('testing-summarized'):
    if not obj.object_name:
      continue

    document = minioObject.GetContentOfBucketObject(
      obj.bucket_name, obj.object_name
    )
    document.Data.update({'id': '', 'document_name': obj.object_name})
    document = json.loads(str(document.Data['content']))

    quotesToProcess = await GetQuotesForDocument(
      document, schemaMatcher, schemaNames
    )
    generatedMatchedDocuments = await MatchCollectionFieldsToDocumentTopics(
      semanticFieldMatcher, document, quotesToProcess, typesenseObject
    )
    typesenseDocuments = await GenerateTypesenseDocuments(
      document,
      llmObject,
      typesenseObject,
      generatedMatchedDocuments,
      obj.object_name,
    )

    UploadToTypesense(typesenseDocuments, typesenseObject)
    response.Data['indexed_documents'] += 1
    yield serverResponse.GenerateServerResponse(response)

  response.Message = 'finished.'
  response.Data['indexed_documents'] = response.Data['total_documents']
  response.Finished = True
  response.Success = True
  yield serverResponse.GenerateServerResponse(response)


def UploadToTypesense(
  generatedDocuments: list[dict[str, str | DocumentSchema]],
  typesenseObject: Typesense_Object,
):
  for document in generatedDocuments:
    schema = str(document['schema'])
    documentSchema = str(document['document']).replace("'", '"')
    typesenseObject.IndexFileIntoCollection(documentSchema, schema)
    # print(response)


async def GetQuotesForDocument(document, schemaMatcher, schemaNames):
  quotes: list[QuoteObject] = []
  for jsonQuote in document:
    quoteObject = QuoteObject(jsonQuote['quote'], jsonQuote['topic'], '')
    (
      closestMatchingSchema,
      score,
    ) = await schemaMatcher.GetBestSchemaForQuoteTopic(quoteObject, schemaNames)
    quoteObject.ClosestMatchingSchemaName = closestMatchingSchema
    quotes.append(quoteObject)
  return quotes


async def MatchCollectionFieldsToDocumentTopics(
  schemaTopicMatcher: SemanticFieldMatcher,
  document,
  quoteObjects: list[QuoteObject],
  typesenseObject: Typesense_Object,
  matchThreshold=0.9,
):
  seenSchemas: list[str] = []
  generatedMatchedDocuments: list[dict[str, dict[str, str | None]]] = []
  for quoteObject in quoteObjects:
    if quoteObject.ClosestMatchingSchemaName in seenSchemas:
      continue  # Document already indexed into this schema
    schema = typesenseObject.GetSchema(quoteObject.ClosestMatchingSchemaName)
    if not schema:
      continue  # Error in fetching the schema
    schema = cast(Dict[str, Any], schema)
    matchedDocument: dict[str, dict[str, str | None]] = {
      'schema': schema['name'],
      'fields': (
        await schemaTopicMatcher.MatchTopicsToSchemaFields(
          document, schema, matchThreshold
        )
      )['fields'],
    }

    seenSchemas.append(quoteObject.ClosestMatchingSchemaName)
    generatedMatchedDocuments.append(matchedDocument)

  return generatedMatchedDocuments


async def GenerateTypesenseDocuments(
  document, llmObject, typesenseObject, generatedMatchedDocuments, documentName
):
  typesenseDocuments: list[dict[str, str | DocumentSchema]] = []

  for matchedDocument in generatedMatchedDocuments:
    convertedDocument, schemaName = await ConvertToTypesenseDocument(
      matchedDocument, document, llmObject, typesenseObject, documentName
    )
    if not convertedDocument:
      continue
    typesenseDocuments.append(
      {'schema': schemaName, 'document': convertedDocument}
    )
  return typesenseDocuments


async def ConvertToTypesenseDocument(
  matchedDocument: dict[str, dict[str, str | None]],
  document,
  llmObject: LLM_Object,
  typesenseObject: Typesense_Object,
  documentName,
):
  schema = typesenseObject.GetSchema(matchedDocument['schema'])  # type: ignore
  if not schema:
    return None, ''

  typesenseDocument: dict[str, Any] = {}

  for field in schema['fields']:
    if field['name'] == 'id' or field['name'] == 'document_name':  # pyright: ignore[reportTypedDictNotRequiredAccess]
      continue  # will be added at the end and we dont want to contaminate this information

    topic = matchedDocument['fields'][field['name']]  # type: ignore
    quote = ''
    for entry in document:
      if entry['topic'] == topic:
        quote = entry['quote']
        break
    if quote == '':
      fieldName = field['name']  # type: ignore
      typesenseDocument.update({fieldName: ''})
      continue

    prompt = f"""Summarize the bellow quote based on the following topic: {topic}
    quote: {quote}
    Only reply with the answer and nothing else. Only respond with the answer."""
    generatedResult = await llmObject.Generate(prompt)

    fieldName = field['name']  # type: ignore
    typesenseDocument.update({fieldName: generatedResult.Response})

  typesenseDocument = DocumentPostProcessing(typesenseDocument, documentName)
  return cast(DocumentSchema, typesenseDocument), schema['name']


def DocumentPostProcessing(generatedDocument, documentName):
  # generatedDocument.update({'id': str(uuid.uuid4())})
  generatedDocument.update({'document_name': documentName})

  return generatedDocument
