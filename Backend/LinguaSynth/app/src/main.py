import json
import re
from typing import cast

from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from fastapi import FastAPI, UploadFile
from ObjectInterfaces.LLM_Object import LLM_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils.LogUtils import ErrorTypes


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


# --- File summarization ---
@app.post('/uploadfile/')
async def UploadContentFile(file: UploadFile) -> ServerResponseObject:
  originalContent = str(await file.read())

  # Only the fields are needed for the document summarization.
  # All other parts are static and should not be changed.
  schemaFields = typesenseObject.GetSchemaFields()
  if len(schemaFields) <= 0:
    return serverResponse.GenerateServerResponse(
      False, 'Error::APIs-UploadFile:: Schema content is empty.'
    )
  # Summarize the uploaded document and format it to match typesense's document format.
  summarizedContent = await llmObject.HandleContentSummarization(
    originalContent, schemaFields
  )
  # Clean out any extra LLM generated text.
  document = __SanitizeJson(summarizedContent.Response)

  # Uploading of the document to MinIO
  uploadResults = await minioObject.UploadNewFileToBucket(
    str(file.filename),
    originalContent,
    document,
  )
  if not uploadResults['summarizedFile'].Success:
    return serverResponse.GenerateServerResponse(
      success=False,
      message='APIs-UploadFile:: Failed to upload file to Minio.',
      errorType=ErrorTypes.Error,
    )

  summarizedFilePath = uploadResults['summarizedFile'].Data['file_path']

  originalFilePath = uploadResults['originalFile'].Data['file_path']
  postgresResults = await postgresObject.UploadFilePathsToDataBase(
    originalFilePath, summarizedFilePath
  )
  postgresObject.client.serverResponseUtil.GenerateLogMessage(
    f'HERE --> {postgresResults}'
  )

  # index the file into typesense.
  schema = typesenseObject.GetSchemaContent()
  collectionName = str(json.loads(schema)['name'])
  typesenseObject.IndexFileIntoCollection(
    file=document,
    fileId=postgresResults.Data['insertedRow'][0],  # 0 is the primary key 'id'
    collectionName=collectionName,
  )

  return serverResponse.GenerateServerResponse(
    success=True, message='Files uploaded and database updated.', errorType=ErrorTypes.Ok
  )


# --- Schema generation ---
@app.post('/generate-schema/')
async def GenerateSchema(file: UploadFile) -> ServerResponseObject:  # pyright: ignore[reportGeneralTypeIssues]
  # TODO:: Sanitize generated schema
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
async def UploadCustomSchema(
  file: UploadFile, force: bool = False
) -> ServerResponseObject:
  content = str(await file.read())
  content = __SanitizeJson(content)
  content = __MutateSchema(content)
  schemaUploadResult = typesenseObject.ImportSchema(content, force)
  if schemaUploadResult.Success:
    return minioObject.UploadSchema(content)
  return schemaUploadResult


def __SanitizeJson(content: str) -> str:
  """
  Extracts the first JSON object from text and normalizes
  it into a single-line valid JSON string.
  """
  # Grab first {...} block
  match = re.search(r'\{[\s\S]*\}', content)
  if not match:
    return ''

  content = match.group(0)
  content = content.replace('\\n', '')

  # Normalize schema (handles double-encoded JSON too)
  content = json.loads(
    json.loads(content) if content.strip().startswith("'") else content
  )
  # Return compact JSON string
  return json.dumps(content, separators=(',', ':'))


def __MutateSchema(schema: str):
  data: dict = json.loads(schema)
  for field in data['fields']:
    if field['name'] == 'databaseID':
      return json.dumps(data, separators=(',', ':'))
  data['fields'].insert(0, {'name': 'databaseID', 'type': 'int64'})
  return json.dumps(data, separators=(',', ':'))


# def __MutateFile(schema: str):
#   data = json.loads(json.loads(schema) if schema.strip().startswith("'") else schema)
#   fields = data['fields']
#   print(f'_mutate d : {fields}')
#   for field in fields:
#     if field['name'] == 'databaseID':
#       return json.dumps(data, separators=(',', ':'))
#   fields.insert(0, {'databaseID', 'type': 'int64'})
#   data['fields'] = fields
#   return json.dumps(data, separators=(',', ':'))
