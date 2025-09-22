import json
import re
from typing import Any, cast

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


# region Document Uploading
# --- File summarization ---
@app.post('/uploadfile')
async def UploadNewDocument(
  document: UploadFile, schemaName: str
) -> ServerResponseObject:
  uploadedDocument = str(await document.read())

  # -- validations
  schemaResult = __HandleSchemaValidation(schema=schemaName)
  if not schemaResult.Success:
    return serverResponse.GenerateServerResponse(
      success=False, message=schemaResult.Message, extraData=schemaResult.Data
    )

  # -- typesense document building
  # only process using the schemas files, everything else will be added later.
  schemaFields = schemaResult.Data['schema']['fields']
  # Summarize the uploaded document and format it to match typesense's document format.
  serverResponse.GenerateLogMessage(
    messageString='Generating summarized version of the document using the given schema.'
  )
  summarizedContent = await llmObject.HandleContentSummarization(
    uploadedDocument, json.dumps(schemaFields)
  )
  summarizedDocumentName = f'{str(document.filename).split(".")[0]}-summarized.{str(document.filename).split(".")[1]}'
  # Clean out any extra LLM generated text.
  generatedDocument = __SanitizeJson(summarizedContent.Response)
  postgresResults = await __HandlePostgresIndexing(
    str(document.filename), summarizedDocumentName
  )
  if not postgresResults.Success:
    return postgresResults

  # Update the database document ID number.
  generatedDocument = json.loads(generatedDocument)
  generatedDocument['databaseID'] = int(
    postgresResults.Data['insertedRow'][0]
  )  # 0 is the primary key 'id'
  # generatedDocument = json.dumps(generatedDocument)

  # Uploading of the document to MinIO
  serverResponse.GenerateLogMessage(messageString='Uploading files to minio server')
  uploadResults = await minioObject.UploadNewFileToBucket(
    fileName=str(document.filename),
    summarizedFilename=summarizedDocumentName,
    originalContent=uploadedDocument,
    summarizedContent=str(generatedDocument),
  )
  if not uploadResults.Data['summarizedFile'].Success:
    return serverResponse.GenerateServerResponse(
      success=False,
      message='APIs-UploadFile:: Failed to upload file to Minio.',
      errorType=ErrorTypes.Error,
    )

  # index the file into typesense.
  typesenseResponse = await __HandleTypesenseIndexing(schemaName, generatedDocument)
  if not typesenseResponse.Success:
    return typesenseResponse

  return serverResponse.GenerateServerResponse(
    success=True,
    message='Upload and summarization completed!',
  )


async def __HandleTypesenseIndexing(
  schemaName: str, content: dict[str, Any]
) -> ServerResponseObject:
  # index the file into typesense.
  return typesenseObject.IndexFileIntoCollection(
    document=content,
    collectionName=schemaName,
  )


async def __HandlePostgresIndexing(
  documentName: str, summarizedDocumentName: str
) -> ServerResponseObject:
  postgresResults = await postgresObject.UploadFilePathsToDataBase(
    documentName, summarizedDocumentName
  )
  return postgresResults


def __HandleSchemaValidation(schema: str) -> ServerResponseObject:
  """
  Validates to see if typesense knows about the schema

  Returns:
    Server Response Object with the valid schema being loaded into Data['schema']
  """
  result = typesenseObject.GetSchema(schema)
  if result is None:
    return typesenseObject.client.serverResponseUtil.GenerateServerResponse(
      success=False,
      message='No schema loaded with that name.',
      errorType=ErrorTypes.Info,
      extraData={},
    )
  return typesenseObject.client.serverResponseUtil.GenerateServerResponse(
    success=True, message=f'{schema} is loaded.', extraData={'schema': result}
  )


# endregion


# region User Questions
@app.post('/question')
async def UserQuestion(searchSchema: str, question: str):
  query = await GenerateQuery(searchSchema, question)
  questionResults = typesenseObject.AskQuestion(searchSchema, query)
  print(questionResults.Data['result'])
  if not questionResults.Success:
    return serverResponse.GenerateServerResponse(
      success=False, message='failed to find information related to users question'
    )
  questionResults = questionResults.Data['results']
  return await llmObject.Generate(
    f"""
    Data: {questionResults}
    Answer the following user question using the data provided.
    User Question: {question}
    """
  )


async def GenerateQuery(searchSchema: str, userQuestion: str):
  schema = typesenseObject.GetSchema(searchSchema)
  schemaFields = schema['fields']  # type: ignore
  # only need the field names for the query generation.
  fieldsNames = []
  for field in schemaFields:
    fieldsNames.append(field['name'])
  print(fieldsNames)
  # TODO:: WE just need to fixe the schema mapping of the types.
  # I think right now it is setting the types wrong.
  prompt = f"""
    You are a query translator that converts natural language questions into valid Typesense JSON search queries.

    ## Instructions:
    - Always return a JSON object with the correct structure for the Typesense Search API.
    - Do not add explanations or text outside the JSON.
    - If the question is vague, choose the most relevant fields.
    - If the user asks for filtering, use `filter_by`.
    - If ranking is implied, use `sort_by`.
    - If multiple fields are relevant, search across them with `q`.

    ## Schema fields:
    {fieldsNames}
      
    ## Example User Questions and Queries:
    Q: "Find books by Isaac Asimov"
    A:
    {{
    'q': "Isaac Asimov",
      "query_by": "author"
    }}

    Q: "science fiction novels after 2010"
    A:
    {{
    'q': "science fiction",
      "query_by": "genre,title,summary",
      "filter_by": "year:>2010"
    }}

    Q: "sort fantasy books by newest"
    A:
    {{
    'q': "fantasy",
      "query_by": "genre,title,summary",
      "sort_by": "year:desc"
    }}
    ---
    ## Task:
    User Question: "{userQuestion}"

    Generate the correct Typesense query JSON: You must include q, query_by, and filter_by in your response.
  """
  result = await llmObject.Generate(prompt)
  return __SanitizeJson(result.Response)


# endregion


# region Schema
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
  content = content.replace("'", '"')
  print(content)
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


# endregion
