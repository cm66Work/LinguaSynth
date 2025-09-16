from typing import cast
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from fastapi import FastAPI, UploadFile, File
from ObjectInterfaces.LLM_Object import LLM_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject


# --- Objects ---
llmObject = LLM_Object()
app = FastAPI()
minioObject = MinIO_Object()
postgresObject = Postgres_Object()

serverResponse = ServerResponse('API', 'api_log')


# --- General ---
@app.get('/')
async def root():
  return {'message:': 'Hello World!'}


@app.get('/healthcheck')
async def HealthCheck():
  return {'message': 'Healthy'}


# --- File summarization ---
@app.post('/uploadfile/')
async def UploadContentFile(file: UploadFile) -> ServerResponseObject:
  # Summarize content, then upload the files
  schema = await minioObject.GetSchemaContent()
  if len(schema) <= 0:
    return serverResponse.GenerateServerResponse(
      False, 'Error::APIs-UploadFile:: Schema content is empty.'
    )

  originalContent = str(await file.read())
  summarizedContent = str(
    await llmObject.HandleContentSummarization(originalContent, schema)
  )
  uploadResults = await minioObject.UploadNewFileToBucket(
    str(file.filename), originalContent, summarizedContent
  )

  if not uploadResults['summarizedFile'].Success:
    return serverResponse.GenerateServerResponse(
      False, 'Error::APIs-UploadFile:: Failed to upload file to Minio.'
    )
  summarizedFilePath = uploadResults['summarizedFile'].Data['file_path']

  originalFilePath = uploadResults['originalFile'].Data['file_path']
  await postgresObject.UploadFilePathsToDataBase(originalFilePath, summarizedFilePath)

  # TODO:: Pass the summarized file into Typesense
  return serverResponse.GenerateServerResponse(
    True, 'Files uploaded and database updated.'
  )


# --- Schema generation ---
@app.post('/generate-schema/')
async def GenerateSchema(file: UploadFile) -> ServerResponseObject:  # pyright: ignore[reportGeneralTypeIssues]
  content = str(await file.read())
  result = cast(
    ServerResponseObject, await llmObject.HandleSchemaGeneration(content=content)
  )
  if not result.Success:
    return serverResponse.GenerateServerResponse(
      False,
      'ERROR::main.upload-file::Schema generation failed!',
      extraData={'result': result},
    )
  return serverResponse.GenerateServerResponse(
    True, 'Schema generated.', extraData={'result': result}
  )


@app.post('/upload-schema/')
async def UploadCustomSchema(file: UploadFile) -> ServerResponseObject:
  content = str(await file.read())
  return minioObject.UploadSchema(content)
