from dataclasses import asdict, dataclass
from typing import Any, cast
from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from fastapi import FastAPI, HTTPException, UploadFile
from Utils.ServerResponse import ServerResponse, ServerResponseV2
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typesense.types.collection import CollectionSchema
import APIs.UploadNewDocument
import APIs.ProcessNewDocuments
import APIs.Schema.Schema
import APIs.CollectionDocumentGenerator
import APIs.Iterate
import APIs.ProcessingPipeline.DocumentIngestionPipeline
import APIs.ProcessingPipeline.QuestionAnsweringPipeline
import APIs.UserQuery
import json
import APIs.ProcessingPipeline


# --- Objects ---
llmObject = LLM_Object()
app = FastAPI()
minioObject = MinIO_Object()
postgresObject = Postgres_Object()
typesenseObject = Typesense_Object()

serverResponse = ServerResponse('API', 'api_log')
serverResponseV2: ServerResponseV2 = ServerResponseV2('API', 'api_log')
NewFileUploader = APIs.UploadNewDocument.Uploader(
  minioObject, serverResponseV2, 'raw-database'
)
DocumentProcessor = APIs.ProcessNewDocuments.DocumentProcessor(
  minioObject, serverResponseV2
)
SchemaGenerator = APIs.Schema.Schema.Schema(
  minioObject, serverResponseV2, llmObject
)
CollectionDocumentGenerator = (
  APIs.CollectionDocumentGenerator.CollectionDocumentGenerator(
    minioObject, llmObject, typesenseObject, serverResponseV2
  )
)
DocumentIngestionPipeline = (
  APIs.ProcessingPipeline.DocumentIngestionPipeline.DocumentIngestionPipeline(
    minioObject, typesenseObject, serverResponseV2
  )
)
QuestionAnsweringPipeline = (
  APIs.ProcessingPipeline.QuestionAnsweringPipeline.QuestionAnsweringPipeline(
    minioObject, typesenseObject, llmObject, serverResponseV2
  )
)

# --- Globals ---
CHUNK_SIZE = 32 * 1024


def __IterBytesInChunks(data: bytes, chunkSize: int = CHUNK_SIZE):
  for i in range(0, len(data), chunkSize):
    yield data[i : i + chunkSize]


# --- General ---
@app.get('/')
async def root():
  return {'message:': 'Hello World!'}


@app.get('/healthcheck')
async def HealthCheck():
  return {'message': 'Healthy'}


@app.post('/question/')
async def UserQuestion(question: str):
  """
  API call for the user asking a question to the systems

  Args::
      question (str): The users question.
  Return:
      Streaming response Event Stream (ServerResponseObject):
      {
          Success (bool): if the operation had succeeded without an internal error, see response message if false.
          Message (str): Returned internal message for the current action or state of system.
          Data ({'answer': generated response as string, 'reference_documents: names of all documents used for answer generation as list[str]})
      }
  """
  schemas: list[CollectionSchema] = await GetAllSchemas()

  async def EventStream():
    async for response in QuestionAnsweringPipeline.Run(question, schemas):
      response = json.dumps(asdict(response)) + '\n'
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')


@app.post('/upload-document/')
async def UploadNewDocument(file: UploadFile):
  """
  API call for uploading a new document to the systems storage.

  Args:
      file (UploadFile): The file to be uploaded to the system
  Return:
      ServerResponseObject: {
          Success (bool): if the operation had succeeded without an internal error, see response message if false.
          Message (str): Returned internal message for the current action or state of system.
          Data (dict): The internal result of the file upload to minio (Ignore and use Success for non debugging actions.)
        }
  """
  result = await NewFileUploader.UploadNewFile(file)
  if not result.Success:
    raise HTTPException(status_code=500, detail=result.Message)
  else:
    raise HTTPException(status_code=200, detail=result.Message)


@app.post('/normalize-uploaded-documents/')
async def NormalizeUploadedDocuments():
  """
  API call for processing un-processed documents into the format the internal system can use.

  Args:
  Return:
      Streaming response Event Stream (ServerResponseObject):
        {
          Success (bool): if the operation had succeeded without an internal error, see response message if false.
          Message (str): Returned internal message for the current action or state of system.
          Data (dict): {
            'document_count' : integer,
            'processed_document_count : integer,
            'document_names: list[str] - list of all documents that have been processed.
          }
        }
  """

  async def EventStream():
    async for response in DocumentProcessor.NormalizeUploadedDocuments(
      'raw-database',
    ):
      # print(response, '\n\n')
      # response = json.dumps(vars(response)) + '\n'
      yield json.dumps(asdict(response)) + '\n'
      # line = (
      #   json.dumps(asdict(response), ensure_ascii=False).encode('utf-8') + b'\n'
      # )

      # for chunk in __IterBytesInChunks(line, CHUNK_SIZE):
      #   # print(chunk, '\n')
      #   yield chunk
      #   await asyncio.sleep(0.1)

  return StreamingResponse(
    EventStream(),
    media_type='application/x-ndjson; charset=utf-8',
    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
  )


@app.post('/generate-schema/')
async def SchemaGeneration(targetBucketName: str):
  """
  API call to manually trigger typesense schema generation on testing schema, used for internal testing only.

  Args:
    bucketName: (str): The name of the bucket which to generate a new schema for.
  Return:
      Streaming response Event Stream (ServerResponseObject):
        {
          Success (bool): if the operation had succeeded without an internal error, see response message if false.
          Message (str): Returned internal message for the current action or state of system.
          Data (dict): {
            'schema' : CollectionSchema - generated typesense collection schema.
          }
        }
  """

  async def EventStream():
    async for response in SchemaGenerator.Generate(targetBucketName):
      # Convert the yielded dict to JSON
      yield json.dumps(asdict(response)) + '\n'
      # schema = response.Data['schema']

      # Now try to upload the new schema
      # async for response in APIs.UploadSchema.UploadSchema(
      #   schema,
      #   serverResponse,
      #   typesenseObject,
      # ):
      #   yield json.dumps(vars(response)) + '\n'

  return StreamingResponse(EventStream(), media_type='application/json')


@app.post('/upload-schema/')
async def UploadSchema(schemaBucket: str, schemaFileName: str) -> bool:
  schema: CollectionSchema = cast(
    CollectionSchema,
    minioObject.GetContentOfBucketObject(schemaBucket, schemaFileName).Data[
      'content'
    ],
  )
  response = typesenseObject.client.client.collections.create(schema)
  # response = typesenseObject.client.RecreateCollection(schema, True)

  # print(schema, '\n')

  # if not response.Success:
  #   raise HTTPException(status_code=500, detail=response.Message)
  # else:
  #   raise HTTPException(status_code=200, detail=response.Message)
  if not response:
    raise HTTPException(status_code=500)
  else:
    raise HTTPException(status_code=200)


class DefaultResponseSuccessModel(BaseModel):
  Success: bool = Field(
    True,
    description='Indicates that the pipeline has completed successfully without any internal errors being raised.',
  )
  Message: str = Field(
    description='String message of the current instal system log whilst processing the pipeline associated to this API'
  )
  Finished: bool = Field(
    True,
    description='Signals that the current pipeline has finished running internally.',
  )


class DefaultResponseFailedModel(DefaultResponseSuccessModel):
  Success: bool = Field(
    False,
    description='Indicates that the pipeline has encountered an internal error at some stage.',
  )
  Message: str = Field(
    description='Internal error or exception log message that was thrown when the internal error occurred'
  )


@dataclass
class IndexingProgressDataModel(BaseModel):
  total_documents: int = Field(
    description='The total number of internal documents that the system has to index before the pipeline is completed'
  )
  processed_documents: int = Field(
    description='The current number of documents that the system has processed.'
  )


class IndexResponseModel(DefaultResponseSuccessModel):
  Data: IndexingProgressDataModel = Field(description='')


# region Generate documents for collection


class DefaultResponseModel(BaseModel):
  Success: bool = Field(
    True,
    description='Indicates that the pipeline has completed successfully without any internal errors being raised.',
  )
  Message: str = Field(
    description='String message of the current instal system log whilst processing the pipeline associated to this API'
  )
  Data: dict[str, Any] = Field(
    default_factory=dict,
    description='Additional data related to the current action.',
  )
  Finished: bool = Field(
    True,
    description='Signals that the current pipeline has finished running internally.',
  )


class Statistic(BaseModel):
  DocumentName: str = Field(
    'document.txt',
    description='The name of the internal document that has been converted into a typesense document collection object and stored inside the internal minio bucket.',
  )
  ProcessingTime: float = Field(
    123.123,
    description='The total time taken for this document to be converted into a typesense document collection object.',
  )


class ResponseObject(BaseModel):
  ProcessName: str = Field(
    description='The internal process name for the conversion of text documents into typesense documents. And the prefix name for the minio bucket where the converted documents are stored. Converted documents are stored in the Process Name with a suffix of "-documents" at the end'
  )
  Statistics: list[Statistic] = Field(
    description='List of statistics collected during the conversion of text documents into typesense documents.'
  )


class GenerateDocumentForCollectionResponses(DefaultResponseModel):
  TotalTimeToComplete: float = Field(
    123.123,
    description='The total time taken for the internal conversion pipeline to complete in ms.',
  )
  AverageTimeToProcessEachDocument: float = Field(
    123.123,
    description='The Calculated time taken for the entire pipeline to process each document. Note that this time should be different to the time per document. This number helps identify the performance of the overall pipeline in ms. Whilst the individual documents processing time shows how different documents sizes impact just the document conversion.',
  )
  DocumentsProcessed: int = Field(
    1,
    description='The current number of documents that have already been processed by the pipeline. Note that this number can be 0 if no documents need to be converted.',
  )
  NumberOfDocumentsToProcess: int = Field(
    1,
    description='The total number of remaining documents to be processed by the pipeline. Note that this number can be 0 if no documents are needed for conversion.',
  )
  CollectionName: str = Field(
    'CollectionSchema',
    description='The typesense schema to use when converting the text documents into typesense document collection objects.',
  )
  IngestionResponseObjects: list[ResponseObject] = Field(
    description='Internal data and statistics collected during the pipelines run process.'
  )


@app.post(
  path='/generate-documents-for-collection/',
  response_class=StreamingResponse,
  responses={
    200: {
      'description': 'Event stream of ServerResponseObject progress containing information related to the current progress of the system as it indexed newly uploaded documents and all processing statistics that where collected during the conversion process',
      'content': {
        'text/event-stream': {
          'schema': GenerateDocumentForCollectionResponses.model_json_schema()
        }
      },
    },
    500: {
      'description': 'Internal server failure occurred during processing.',
      'content': {
        'text/event-stream': {
          'schema': DefaultResponseModel.model_json_schema()
        }
      },
    },
  },
)
async def GenerateDocumentsForCollection(
  targetDataBucket: str, collectionName: str
):
  """
  Converts documents in the target data bucket to match the collection schema name.
  Outputs the converted documents to their own bucket whose name is the name of the target data bucket + '-documents'
  E.G. targetDataBucket = 'token-extraction' will result in the generation of a new bucket called 'token-extraction-documents'
  """

  async def EventStream():
    async for response in CollectionDocumentGenerator.RunGenerators(
      targetDataBucket, collectionName
    ):
      response = json.dumps(asdict(response)) + '\n'
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')


# endregion


# region Collection document Ingestion
class CollectionDocumentIngestionResponseModel(DefaultResponseModel):
  TotalRunTime: float = Field(
    123.123,
    description='The total time taken for the internal conversion pipeline to complete in ms.',
  )
  TotalTimeDividedByDocuments: float = Field(
    123.123,
    description='The Calculated time taken for the entire pipeline to process each document. Note that this time should be different to the time per document. This number helps identify the performance of the overall pipeline in ms. Whilst the individual documents processing time shows how different documents sizes impact just the document conversion.',
  )
  DocumentsProcessed: int = Field(
    1,
    description='The current number of documents that have already been processed by the pipeline. Note that this number can be 0 if no documents need to be converted.',
  )
  TotalNumberOfDocuments: int = Field(
    1,
    description='The total number of remaining documents to be processed by the pipeline. Note that this number can be 0 if no documents are needed for conversion.',
  )
  CollectionName: str = Field(
    'CollectionSchema',
    description='The typesense schema to use when converting the text documents into typesense document collection objects.',
  )
  ResponseObjects: list[ResponseObject] = Field(
    description='Internal data and statistics collected during the pipelines run process.'
  )


@app.post(
  path='/document-ingestion',
  response_class=StreamingResponse,
  responses={
    200: {
      'description': 'Event stream of ServerResponseObject progress containing information related to the current progress of the system as it indexed documents into the target collection and all processing statistics that where collected during the conversion process',
      'content': {
        'text/event-stream': {
          'schema': CollectionDocumentIngestionResponseModel.model_json_schema()
        }
      },
    },
    500: {
      'description': 'Internal server failure occurred during processing.',
      'content': {
        'text/event-stream': {
          'schema': DefaultResponseModel.model_json_schema()
        }
      },
    },
  },
)
async def DocumentIngestion(targetDataBucket: str, collectionName: str):
  """
  Indexes all documents from the targetDataBucket into the given collectionName
  """

  async def EventStream():
    async for response in DocumentIngestionPipeline.Run(
      targetDataBucket, collectionName
    ):
      response = json.dumps(asdict(response)) + '\n'
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')


# endregion


@app.post('/delete-all-schemas/')
async def DeleteAllSchemas():
  for schema in typesenseObject.GetAllSchemas():
    typesenseObject.DeleteSchema(schema['name'])


@app.post('/get-all-schemas/')
async def GetAllSchemas() -> list[CollectionSchema]:
  schemas = typesenseObject.GetAllSchemas()
  print(f'\n Loaded schemas: {schemas}')
  return schemas


@app.post('/iterate/')
async def IterateAPI():
  return await APIs.Iterate.Iterate(typesenseObject, minioObject)
