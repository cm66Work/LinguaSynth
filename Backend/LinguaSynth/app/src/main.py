import json
import APIs.UserQuery
from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from fastapi import FastAPI, UploadFile
from Utils.ServerResponse import ServerResponse
import APIs.UploadNewDocument
import APIs.ProcessNewDocuments
import APIs.GenerateSchema
import APIs.UploadSchema
import APIs.IndexNewDocuments
import APIs.DocumentIndexing
from fastapi.responses import StreamingResponse

# --- Objects ---
llmObject = LLM_Object()
app = FastAPI()
minioObject = MinIO_Object()
postgresObject = Postgres_Object()
typesenseObject = Typesense_Object()

serverResponse = ServerResponse('API', 'api_log')


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

  async def EventStream():
    async for response in APIs.UserQuery.UserQuery(
      serverResponse, llmObject, typesenseObject, question
    ):
      response = json.dumps(vars(response)) + '\n'
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
  return await APIs.UploadNewDocument.UploadNewDocument(
    'testing', file, minioObject, serverResponse
  )


@app.post('/process-new-uploaded-documents/')
async def ProcessNewDocuments():
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
    async for response in APIs.ProcessNewDocuments.ProcessNewDocuments(
      'testing',
      serverResponse,
      minioObject,
      llmObject,
      postgresObject,
      1,
    ):
      response = json.dumps(vars(response)) + '\n'
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')


@app.post('/generate-schema/')
async def SchemaGeneration():
  """
  API call to manually trigger typesense schema generation on testing schema, used for internal testing only.

  Args:
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
    async for response in APIs.GenerateSchema.SchemaGeneration(
      minioObject, llmObject, typesenseObject, serverResponse
    ):
      # Convert the yielded dict to JSON
      yield json.dumps(vars(response)) + '\n'
      schema = response.Data['schema']

      # Now try to upload the new schema
      async for response in APIs.UploadSchema.UploadSchema(
        schema,
        serverResponse,
        typesenseObject,
      ):
        yield json.dumps(vars(response)) + '\n'

  return StreamingResponse(EventStream(), media_type='application/json')


@app.post('/start-indexing-documents/')
async def StartDocumentIndexing():
  """
  API call to index orphaned documented into their relevant typesense collections.

  Args:
  Return:
      Streaming response Event Stream (ServerResponseObject):
        {
          Success (bool): if the operation had succeeded without an internal error, see response message if false.
          Message (str): Returned internal message for the current action or state of system.
          Data (dict): {
            'total_documents': integer,
            'processed_documents': integer
          }
        }
  """

  async def EventStream():
    async for response in APIs.DocumentIndexing.IndexNewDocuments(
      serverResponse, typesenseObject, minioObject, llmObject
    ):
      response = json.dumps(vars(response)) + '\n'
      print('response: ', response)
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')


@app.post('/delete-all-schemas/')
async def DeleteAllSchemas():
  for schema in typesenseObject.GetAllSchemas():
    typesenseObject.DeleteSchema(schema['name'])


@app.post('/get-all-schemas')
async def GetAllSchemas():
  return typesenseObject.GetAllSchemas()
