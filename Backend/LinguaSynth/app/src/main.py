import json
from typing import Any

from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from fastapi import FastAPI, UploadFile
from ObjectInterfaces.LLM_Object import LLM_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils.LogUtils import ErrorTypes
from Utils import JsonUtils


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
  # -- validations
  schemaResult = __HandleSchemaValidation(schema=schemaName)
  if not schemaResult.Success:
    return serverResponse.GenerateServerResponse(
      success=False, message=schemaResult.Message, extraData=schemaResult.Data
    )

  schemaFields = json.loads(schemaResult.Data['schema'])['fields']
  # -- typesense document building
  # only need the field names and types for the query generation.
  # response = schemaResult.Data['schema']['fields']
  fields = {}
  # --- this is the structure at this point.
  # list [ dict [ str, str, str, str, ... ] ]
  for field in schemaFields:
    field_obj = {field['name']: field['type']}
    fields.update(field_obj)
  # Summarize the uploaded document and format it to match typesense's document format.
  serverResponse.GenerateLogMessage(
    messageString='Generating summarized version of the document using the given schema.'
  )
  uploadedDocument = str(await document.read())
  uploadedDocument = uploadedDocument.replace("'", '')
  jsonSchemaFields = JsonUtils.ConvertToJsonSchema(fields)
  summarizedContent = await llmObject.HandleContentSummarization(
    uploadedDocument, json.loads(jsonSchemaFields)
  )
  print(summarizedContent.Response)

  # Clean out any extra LLM generated text.
  summarizedJson = JsonUtils.SanitizeJson(summarizedContent.Response)
  generatedDocument = summarizedJson[0]
  message = generatedDocument
  success = summarizedJson[1]

  if not success:
    return serverResponse.GenerateServerResponse(
      success=False, message=f'Failed to summarize uploaded content. {message}'
    )

  summarizedDocumentName = f'{str(document.filename).split(".")[0]}-summarized.{str(document.filename).split(".")[1]}'
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
    extraData={
      'typesenseResponse': typesenseResponse,
      'postgresResponse': postgresResults,
    },
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
async def UserQuestion(
  searchSchema: str, question: str, minHits: int = 2, maxHits: int = 20
):
  query = await GenerateQuery(searchSchema, question)
  query = json.loads(query[0])
  query['filter_by'] = 'first_appearance_year:>-1'
  query.pop('filter_by')

  query = json.dumps(query)
  questionResults = typesenseObject.AskQuestion(searchSchema, query, minHits, maxHits)
  # print(questionResults)
  if not questionResults.Success or questionResults.Data == {}:
    return serverResponse.GenerateServerResponse(
      success=False, message='failed to find information related to users question'
    )
  questionResults = questionResults.Data
  document = questionResults.get('documents', [])
  # limit the amount of information the model gets fed.
  # helps produce more accurate results.
  print(len(document))
  if (len(document)) > 0:
    document = document[0][
      'document'
    ]  # only take the first, top most relevance from the search.
  # Responses.
  prompt = ''
  if questionResults['confidence'] != 1:
    prompt = f'{questionResults["responseMessage"]} \n {question}'
  else:
    prompt = f"""
    Documents: {document}
    User Question: {question}

    Summarize the document to answer the users question.
    return your answer within 50 words.
    """
  result = await llmObject.Generate(prompt, think=True)
  result.Data = {'questionResults': questionResults}
  return result


async def GenerateQuery(searchSchema: str, userQuestion: str):
  schema = json.loads(typesenseObject.GetSchema(searchSchema))

  schemaFields = schema['fields']  # type: ignore
  # only need the field names and types for the query generation.
  fields = {}
  for field in schemaFields:
    summarizedField = {f'{field["name"]}': f'{field["type"]}'}
    fields.update(summarizedField)
  prompt = f"""

    You are a query generator. Convert a user question into a valid Typesense search query JSON.

    Rules:
    - Only include string or string[] fields in "query_by".
    - Use numeric or date fields only in "filter_by" or "sort_by".
    - Always return only JSON, no explanations.

    Example:
    Q: "Find books by Isaac Asimov"
    A:
    {{
    'q': "Isaac Asimov",
      "query_by": "author",
      "filter_by": "year:>2010",
    }}

    Q: "science fiction novels after 2010"
    A:
    {{
    'q': "science fiction",
      "query_by": "genre,title,summary"
      "filter_by": "year:>2010",
      "sort_by": "year:desc",
    }}

    Schema fields:
    {fields}

    User question:
    {userQuestion}

    Generate the correct Typesense query JSON:
    You must include q, query_by, and filter_by in your response.
    You must include q, query_by, and filter_by in your response.
  """
  result = await llmObject.Generate(prompt)
  return JsonUtils.SanitizeJson(result.Response)


# endregion


# region Schema
@app.post('/generate-schema/')
async def GenerateSchema(
  schemaName: str, file: UploadFile, force: bool = False
) -> ServerResponseObject:  # pyright: ignore[reportGeneralTypeIssues]
  content = str(await file.read())
  result = await llmObject.HandleSchemaGeneration(schemaName=schemaName, content=content)
  generatedCategories = JsonUtils.SanitizeJson(result.Response)
  if not generatedCategories[1]:  # Sanitize did not work.
    return serverResponse.GenerateServerResponse(
      False,
      'ERROR::main.upload-file::Schema generation failed!',
      extraData={'result': generatedCategories[0]},
    )
  try:
    content = str(generatedCategories[0]).replace('\\', '')
    schemaUploadResult = typesenseObject.ImportSchema(content, force)
    if schemaUploadResult.Success:
      return minioObject.UploadSchema(content, schemaName)
    return schemaUploadResult
  except Exception as e:
    return serverResponse.GenerateServerResponse(
      success=False,
      message='Failed to upload schema.',
      extraData={'response': generatedCategories[0], 'exception': e},
    )


@app.post('/upload-schema/')
async def UploadCustomSchema(
  file: UploadFile, schemaName: str, force: bool = False
) -> ServerResponseObject:
  content = str(await file.read())
  content = JsonUtils.SanitizeJson(content)
  content = __MutateSchema(content[0])
  schemaUploadResult = typesenseObject.ImportSchema(content, force)
  if schemaUploadResult.Success:
    return minioObject.UploadSchema(content, schemaName)
  return schemaUploadResult


def __MutateSchema(schema: str):
  data: dict = json.loads(schema)
  for field in data['fields']:
    if field['name'] == 'databaseID':
      return json.dumps(data, separators=(',', ':'))
  data['fields'].insert(0, {'name': 'databaseID', 'type': 'int64'})
  return json.dumps(data, separators=(',', ':'))


# endregion


# region document Uploading
# Uploading documents to the server so that we can process them for later tasks.
@app.post('/upload-document-original/')
async def UploadDocumentOriginal(
  documentCategory: str, file: UploadFile
) -> ServerResponseObject:
  # upload the document and store it in the database
  content = (await file.read()).decode('utf-8')
  result = await UploadDocument(
    f'{documentCategory}-originals',
    content,
    fileName=file.filename if file.filename is not None else 'tempt.txt',
  )
  if not result.Success:
    return result

  return serverResponse.GenerateServerResponse(
    success=True,
    message=f'original document {file.filename} uploaded.',
    extraData={'result': result},
  )


async def UploadDocument(
  bucketName: str, content: str, fileName: str
) -> ServerResponseObject:
  """Uploads the document to bucket and stores its reference in the database"""
  # Upload the file to the storage server.
  result = minioObject.UploadDocumentToStorageServer(bucketName, content, fileName)
  if not result.Success:
    return result

  # Upload the file name to our referencing database
  result = await postgresObject.UploadOriginalDocument(
    f'documentReference_{bucketName}', f'{bucketName}/{fileName}'
  )
  if not result.Success:
    return result

  # document upload complete
  return serverResponse.GenerateServerResponse(
    success=True,
    message='Document Upload complete',
  )


async def UploadSummarizedDocument(
  originalBucketName: str,
  summarizedBucketName: str,
  summarizedContent: str,
  originalFileName: str,
  summarizedFileName: str,
) -> ServerResponseObject:
  """Uploads the summarized document to bucket and stores the summarized and original reference in the database"""
  # Upload the file to the storage server.
  result = minioObject.UploadDocumentToStorageServer(
    summarizedBucketName, summarizedContent, summarizedFileName
  )
  if not result.Success:
    return result

  # Upload the file name to our referencing database
  result = await postgresObject.UploadSummarizedDocument(
    f'summarizedDocumentReference_{summarizedBucketName}',
    f'{originalBucketName}/{originalFileName}',
    f'{summarizedBucketName}/{summarizedFileName}',
  )
  if not result.Success:
    return result

  # document upload complete
  return serverResponse.GenerateServerResponse(
    success=True,
    message='Summarized document Upload complete',
  )


# endregion


# region Document summarization and processing
# Process all original documents to summarized formats.
# is later used to indexing into Typesense.
@app.post('/process-original-documents/')
async def ProcessOriginalDocuments(
  originalBucketRootName: str, resolution: int = 1
) -> ServerResponseObject:
  # summarize all documents in the target category,
  # and save the results into a separate bucket.
  # We do not need typesense to process entire documents for indexing and document generation.
  # We need to reduce the amount of data that is bing processed by Typesense.
  originalBucketName = f'{originalBucketRootName}-originals'
  if not await minioObject.BucketExists(originalBucketName):
    return serverResponse.GenerateServerResponse(
      success=False,
      message=f'No bucket with name: {originalBucketName}',
      errorType=ErrorTypes.Error,
      className=__name__,
    )

  uploadedSummarizedDocumentNames = []
  # Get all original documents in the storage bucket.
  for document in minioObject.GetObjectsInBucket(originalBucketName):
    # For each document, generate summarized document
    if document.object_name is None:
      serverResponse.GenerateLogMessage(
        messageString=f'Tried to process a document with no name from bucket: {originalBucketName}, skipping file.'
      )
      continue
    result = minioObject.GetContentOfBucketObject(
      originalBucketName, document.object_name
    )
    if not result.Success:
      serverResponse.GenerateLogMessage(
        messageString=f'Failed to get content from file: {document.object_name.split(".")[0]}, from bucket: {originalBucketName}, skipping file.'
      )
      continue
    print('\n ----- New document')
    summarizedDocumentContent = await SummarizeDocument(
      content=result.Data['content'],
      context=f'{originalBucketRootName} and {document.object_name}',
      resolution=resolution,
    )
    if len(summarizedDocumentContent) <= 0:
      serverResponse.GenerateLogMessage(
        messageString=f'document: {document.object_name} summarized to nothing, skipping file.',
        errorType=ErrorTypes.Warning,
      )
      continue
    # Upload summarized document into their own bucket and store a reference in the database table.
    # story both the original document path and the summarized document path.
    summarizedDocumentName = f'{document.object_name.split(".")[0]}-summarized.txt'
    summarizedBucketName = f'{originalBucketRootName}-summarized'
    result = await UploadSummarizedDocument(
      originalBucketName,
      summarizedBucketName,
      summarizedDocumentContent,
      document.object_name,
      summarizedDocumentName,
    )
    if not result.Success:
      serverResponse.GenerateLogMessage(
        messageString=f'failed to upload: {summarizedDocumentName} to bucket: {summarizedBucketName}, skipping file.'
      )
      continue
    serverResponse.GenerateLogMessage(
      messageString=f'Summarized document: {summarizedDocumentName} has been uploaded successfully.'
    )
    uploadedSummarizedDocumentNames.append(summarizedDocumentName)

  return serverResponse.GenerateServerResponse(
    success=len(uploadedSummarizedDocumentNames) > 0,
    message=f'finished uploading {len(uploadedSummarizedDocumentNames)} summarized documents:',
    extraData={'summarizedDocumentNames': uploadedSummarizedDocumentNames},
  )


async def SummarizeDocument(content: str, context: str, resolution: int) -> str:
  """
  Summarizes the given content's paragraphs content by the resolution
  For example if a resolution of 2 is given, then each paragraph of the content will be summarized twice.

  Args:
      content (str): The content to be summarized.
      resolution (int): The number of times the content gets summarized. Higher values result in smaller resulted document sizes but has higher data loss.
  """
  summarizedContent = ''
  for paragraph in content.split('\n\n'):
    if len(paragraph) <= 0:
      continue
    summarizedParagraph = await llmObject.GenerateV2(
      f"""paragraph: {paragraph} \n summarize the paragraph into 75% of its original length using the context: {context}. Only reply with the summarized content and do not write anything else or respond to this prompt."""
    )
    if not summarizedParagraph.Success:
      continue
    summarizedContent = str().join(
      [summarizedContent, '\n\n', summarizedParagraph.Response]
    )
  print(f'summarizedContent: {summarizedContent}')

  resolution -= 1
  if resolution > 0:
    return await SummarizeDocument(summarizedContent, context, resolution)
  return summarizedContent


# endregion
