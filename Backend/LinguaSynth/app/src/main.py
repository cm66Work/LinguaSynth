import json
from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from fastapi import FastAPI, UploadFile
from Utils.ServerResponse import ServerResponse
from Utils import JsonUtils
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


# async def __HandleTypesenseIndexing(
#   schemaName: str, content: dict[str, Any]
# ) -> ServerResponseObject:
#   # index the file into typesense.
#   return typesenseObject.IndexFileIntoCollection(
#     document=content,
#     collectionName=schemaName,
#   )


# async def __HandlePostgresIndexing(
#   documentName: str, summarizedDocumentName: str
# ) -> ServerResponseObject:
#   postgresResults = await postgresObject.UploadFilePathsToDataBase(
#     documentName, summarizedDocumentName
#   )
#   return postgresResults


# def __HandleSchemaValidation(schema: str) -> ServerResponseObject:
#   """
#   Validates to see if typesense knows about the schema

#   Returns:
#     Server Response Object with the valid schema being loaded into Data['schema']
#   """
#   result = typesenseObject.GetSchema(schema)
#   if result is None:
#     return typesenseObject.client.serverResponseUtil.GenerateServerResponse(
#       success=False,
#       message='No schema loaded with that name.',
#       errorType=ErrorTypes.Info,
#       extraData={},
#     )
#   return typesenseObject.client.serverResponseUtil.GenerateServerResponse(
#     success=True, message=f'{schema} is loaded.', extraData={'schema': result}
#   )


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
  questionResults = typesenseObject.AskQuestion(
    searchSchema, query, minHits, maxHits
  )
  # print(questionResults)
  if not questionResults.Success or questionResults.Data == {}:
    questionResults.Message = (
      'Failed to find information related to users question.'
    )
    return serverResponse.GenerateServerResponse(questionResults)
  questionResults = questionResults.Data
  document = questionResults.get('documents', [])
  # limit the amount of information the model gets fed.
  # helps produce more accurate results.
  # print(len(document))
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
  schema = typesenseObject.GetSchema(searchSchema)
  if schema is None:
    return []
  schema = json.loads(str(schema))

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


# Uploading documents to the server so that we can process them for later tasks.
@app.post('/upload-document/')
async def UploadNewDocument(documentCategory: str, file: UploadFile):
  return await APIs.UploadNewDocument.UploadNewDocument(
    documentCategory, file, minioObject, serverResponse
  )


# region Document summarization and processing
# Process all original documents to summarized formats.
# is later used to indexing into Typesense.
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


# region Schema generation
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


# endregion


# region Schema Uploading
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


# uploaded the passed schema string to typesense.

# endregion


# region Document indexing
# Index all summarized documents into typesense
# files that have been indexed are marked in some way so that they can be skipped
# if indexing is done again in the future.
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
      yield response

  return StreamingResponse(EventStream(), media_type='application/json')


# endregion
