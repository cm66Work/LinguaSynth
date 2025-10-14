import json
import re
from typing import Any, List, cast
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.LogUtils import ErrorTypes
from Utils.ServerResponse import ServerResponse, ServerResponseObject


async def IndexNewDocuments(
  schemaName: str,
  serverResponse: ServerResponse,
  typesenseObject: Typesense_Object,
  postgresObject: Postgres_Object,
  minioObject: MinIO_Object,
  llmObject: LLM_Object,
):
  """
  Indexes new documents from minio to the given typesense schema.
  Args:
      schemaName: str : the schema name.
      serverResponse: ServerResponse: server Response for the API calls and logging.
      typesenseObject: Typesense_Object: typesense interface.
      postgresObject: Postgres_Object: postgres interface.
      minioObject: MinIO_Object: minio interface.
      llmObject: LLM_Object: llm interface
  """
  extraData = {'total_documents': -1, 'processed_documents': -1}
  currentResponse = ServerResponseObject()
  currentResponse.Data = extraData
  currentResponse.Message = 'Processing....'
  yield serverResponse.GenerateServerResponse(currentResponse)

  if not typesenseObject.SchemaExists(schemaName):
    currentResponse.Success = False
    currentResponse.Message = f'No schema with name: {schemaName}'
    currentResponse.Data = extraData
    currentResponse.Finished = True
    yield serverResponse.GenerateServerResponse(
      currentResponse, errorType=ErrorTypes.Error, className='IndexNewDocument'
    )
    return

  processedDocumentsBucketName = f'{schemaName}-summarized'
  currentResponse.Data['total_documents'] = (
    minioObject.GetNumberOfObjectsInBucket(processedDocumentsBucketName)
  )
  schema = typesenseObject.GetSchema(schemaName)
  if schema is None:
    currentResponse.Message = f'Failed to get schema: {schemaName}'
    currentResponse.Finished = True
    yield serverResponse.GenerateServerResponse(currentResponse)
    return

  # we only need the schema fields
  currentResponse.Message = 'Loading schema...'
  currentResponse.Data['processed_documents'] = 0
  yield serverResponse.GenerateServerResponse(currentResponse)

  ## for each file -> for each paragraph,
  for document in minioObject.GetObjectsInBucket(processedDocumentsBucketName):
    print('\n document')
    if document.object_name is None:
      currentResponse.Message = (
        f'Failed to get content form bucket {processedDocumentsBucketName}'
      )
      yield serverResponse.GenerateServerResponse(currentResponse)
      return
    currentResponse.Data['processed_documents'] += 1
    yield serverResponse.GenerateServerResponse(currentResponse)
    minioResults = minioObject.GetContentOfBucketObject(
      processedDocumentsBucketName, document.object_name
    )
    if not minioResults.Success:
      currentResponse.Message = (
        f'Failed to get content from file:{document.object_name.split(".")[0]}'
      )
      yield serverResponse.GenerateServerResponse(currentResponse)
      return

    currentResponse.Message = 'Generating document from schema'
    yield serverResponse.GenerateServerResponse(currentResponse)

    try:
      schemaFields = schema['fields']
      GeneratedDocument = await GenerateDocument(
        schemaFields, minioResults.Data['content'], llmObject
      )
      # # TODO:: Add in the 'document_id' using the postgres entry ID
      result = typesenseObject.IndexFileIntoCollection(
        json.dumps(GeneratedDocument), schemaName
      )

      currentResponse.Message = result.Message
      currentResponse.Success = result.Success
      yield serverResponse.GenerateServerResponse(currentResponse)

    except Exception as e:
      print(f'failed to index {e}')

    # Finally index the generated document.
    # -- if it fails then we add it to a list, if it succeeds then we migrate the document to
    # -- a new bucket in minio os we do not index it again.
    # --- Update the postgres entry for that document so wen can keep track of it.
  currentResponse.Finished = True
  if currentResponse.Success:
    currentResponse.Message = 'finished indexing new documents'
  else:
    currentResponse.Message = 'Failed to index documents'
  yield serverResponse.GenerateServerResponse(currentResponse)


async def GenerateDocument(
  schemaFields: List,
  document: str,
  llmObject: LLM_Object,
  maxResponseCount: int = 5,
  generatedDocument: dict[str, Any] = {},
):
  if not schemaFields:
    return generatedDocument

  currentField = schemaFields.pop()
  fieldType = currentField['type']
  fieldName = currentField['name']

  # ugly brute force method
  # types are copied on the typesense collection types.
  # print(f'\n name: {fieldName}, type: {fieldType}')
  async def ProcessFieldTypes(fieldType: str) -> Any:
    match fieldType:
      case 'string':
        llmResponse = await llmObject.GenerateV2(
          f"""document:{document} \n Summarize the content of this document based on the following topic: {fieldName}. Only response with the summarized content. Only response as a {fieldType}. Your response should be a max of {maxResponseCount} words."""
        )
        return llmResponse.Response
      case 'int32' | 'int64':
        llmResponse = await llmObject.GenerateV2(
          f"""document:{document} \n find the numerical information in this document that is relevant to the following topic: {fieldName}. Only response with the summarized content. Only response as a {fieldType}. Your response should be a max of 1 number"""
        )
        llmResponse = re.search(r'([1-9][0-9]*)', llmResponse.Response)
        if llmResponse is None:
          llmResponse = 0
        else:
          llmResponse = cast(int, llmResponse.group(0))
        return int(llmResponse)
      case 'float':
        llmResponse = await llmObject.GenerateV2(
          f"""document:{document} \n find the numerical information in this document that is relevant to the following topic: {fieldName}. Only response with the summarized content. Only response as a {fieldType}. Your response should be a max of 1 floating point number limited to 3 decimal places"""
        )
        llmResponse = re.search(
          r'([1-9][0-9]*.[1-9][0-9]*)', llmResponse.Response
        )
        if llmResponse is None:
          llmResponse = 0.0
        else:
          llmResponse = cast(float, llmResponse.group(0))
        return float(llmResponse)
      case 'bool':
        llmResponse = await llmObject.GenerateV2(
          f"""document:{document} \n Does this document answer the following question? Question: {fieldName}. Only response as a {fieldType} answer. Your response should be a max of 1 True or False response."""
        )
        llmResponse = (
          llmResponse.Response[0].capitalize() + llmResponse.Response[1::]
        )
        llmResponse = cast(bool, llmResponse)
        return bool(llmResponse)
      case 'bool[]':
        llmResponse = await llmObject.GenerateV2(
          f"""document:{document} \n Does this document answer the following question? Question: {fieldName}. Only response as a list of True or False answer. Your response should be a max of {maxResponseCount} True or False response."""
        )
        # TODO:: need to add this
        llmResponse = [False, False, False]
        return list[bool(llmResponse)]
      case 'geopoint' | 'geopolygon':
        # TODO:: need to add this
        return 'Handle geographic field'
      case 'geopoint[]':
        # TODO:: need to add this
        return 'Handle array of geopoints'
      case 'string[]':
        llmResponse = await llmObject.GenerateV2(
          f"""document:{document} \n Summarize the content of this document based on the following topic: {fieldName}. Only response with the summarized content. Only response as a list of strings that are related to the answer. Reach list string should be a max of {maxResponseCount} words. Only response with the answer as a Json List of strings"""
        )
        llmResponse = re.search(r'\[[\s\S]*\]', llmResponse.Response)
        if llmResponse is None:
          llmResponse = ''
        else:
          llmResponse = str().join(
            line.strip() for line in llmResponse.group(0).splitlines()
          )
          llmResponse = llmResponse[1:-1]
          llmResponse = llmResponse.replace('"', '')
        return llmResponse.split(',')
      case 'int32[]' | 'int64[]' | 'float[]':
        return [123, 456, 789]
      case 'object':
        return {}
      #   objectResult = await GenerateDocument(
      #     currentField['fields'], document, llmObject
      #   )
      #   print(f'\n objectResult: {objectResult}')
      #   # return ProcessDocumentObjectGeneration(
      #   #   document, fieldName, currentField['fields'], llmObject
      #   # )
      #   return objectResult
      case 'object[]':
        return [{}]
        # objectResult = await GenerateDocument(
        #   currentField['fields'], document, llmObject
        # )
        # print(f'\n objectResult: {objectResult}')
        # # return ProcessDocumentObjectGeneration(
        # #   document, fieldName, currentField['fields'], llmObject
        # # )
        # return objectResult
      case 'auto':
        return 'Handle automatic type inference'
      case 'string*':
        return 'Handle special wildcard string type'
      case 'image':
        return 'Handle image type'
      case _:
        return None

  temp = await ProcessFieldTypes(fieldType)
  # print(type(temp))
  generatedDocument.update({fieldName: temp})
  return await GenerateDocument(
    schemaFields, document, llmObject, maxResponseCount, generatedDocument
  )


async def ProcessDocumentObjectGeneration(
  document: str, fieldName: str, llmObject: LLM_Object, objectFields
):
  # TODO:: need to test.
  print(f'\n object fields: {objectFields}')
  llmResponse = await llmObject.GenerateV2(
    f"""document:{document} \n Use this document to generate an JSON object that best aligns with and matches the following topic: {fieldName}. Response with a single valid Json only. Output format is {objectFields}"""
  )

  llmResponse = re.search(r'(\{[\s\S]*\})', llmResponse.Response)
  if llmResponse is None:
    llmResponse = {}
  else:
    llmResponse = str().join(
      line.strip() for line in llmResponse.group(0).splitlines()
    )

  try:
    llmResponse = json.loads(str(llmResponse))
    return llmResponse
  except Exception:
    print('failed object: ', llmResponse)
    return {}
