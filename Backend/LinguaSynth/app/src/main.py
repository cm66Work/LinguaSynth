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


@app.post('/question')
async def UserQuestion(question: str):
  async def EventStream():
    async for response in APIs.UserQuery.UserQuery(
      serverResponse, llmObject, typesenseObject, question
    ):
      response = json.dumps(vars(response)) + '\n'
      print('response', response)
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')


@app.post('/upload-document/')
async def UploadNewDocument(documentCategory: str, file: UploadFile):
  return await APIs.UploadNewDocument.UploadNewDocument(
    documentCategory, file, minioObject, serverResponse
  )


@app.post('/process-new-uploaded-documents/')
async def ProcessNewDocuments(bucketRootName: str, resolution: int = 1):
  async def EventStream():
    async for response in APIs.ProcessNewDocuments.ProcessNewDocuments(
      bucketRootName,
      serverResponse,
      minioObject,
      llmObject,
      postgresObject,
      resolution,
    ):
      response = json.dumps(vars(response)) + '\n'
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')


@app.post('/generate-schema/')
async def SchemaGeneration(
  bucketRootName: str,
  sampleSize: int,
  resolution: int = 1,
  force: bool = False,
  tagCompression: float = 0.25,
):
  """

  Args:
      bucketRootName: str
      sampleSize: int
      resolution: int = 1
      force: bool = False
      tagCompression:float = 0.25 : tag similarity matching for quote combining.
  """

  async def EventStream():
    # Iterate over the inner async generator
    async for response in APIs.GenerateSchema.SchemaGeneration(
      bucketRootName=bucketRootName,
      sampleSize=sampleSize,
      serverResponse=serverResponse,
      minioObject=minioObject,
      llmObject=llmObject,
      resolution=resolution,
      force=force,
      tagCompression=tagCompression,
    ):
      # Convert the yielded dict to JSON
      response = json.dumps(vars(response)) + '\n'
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')


@app.post('/upload-schema/')
async def UploadJsonSchema(schemaName: str, schema: str, force: bool = False):
  """
  Uploads the given schema as a new typesense collection schema.

  Args:
      schemaName: str : the schemas name.
      schemaJsonString: str : the json string for the schema.
      force : bool : if true then it will override any existing schemas with the same name.
  """

  async def EventStream():
    async for response in APIs.UploadSchema.UploadSchema(
      schemaName,
      schema,
      serverResponse,
      typesenseObject,
      force,
    ):
      response = json.dumps(vars(response)) + '\n'
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')


@app.get('/get-schemas/')
async def GetLoadedSchemas():
  return typesenseObject.GetAllSchemas()


@app.post('/start-indexing-documents/')
async def StartDocumentIndexing(schemaName: str):
  """
  Starts indexing new documents into the server using AI.
  Args:
      schemaName: str : the schemas name.
  """

  async def EventStream():
    async for response in APIs.IndexNewDocuments.IndexNewDocuments(
      schemaName=schemaName,
      serverResponse=serverResponse,
      typesenseObject=typesenseObject,
      postgresObject=postgresObject,
      minioObject=minioObject,
      llmObject=llmObject,
    ):
      response = json.dumps(vars(response)) + '\n'
      print('response: ', response)
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')
