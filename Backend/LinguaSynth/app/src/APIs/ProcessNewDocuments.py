import json
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from Utils import JsonUtils
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils.LogUtils import ErrorTypes


# region Document summarization and processing
# Process all original documents to summarized formats.
# is later used to indexing into Typesense.
async def ProcessNewDocuments(
  bucketRootName: str,
  serverResponse: ServerResponse,
  minioObject: MinIO_Object,
  llmObject: LLM_Object,
  postgresObject: Postgres_Object,
  resolution: int = 1,
):
  extraData = {
    'document_count': 0,
    'processed_document_count': 0,
    'DocumentNames': '',
  }
  currentResponse = ServerResponseObject()
  currentResponse.Data = extraData
  currentResponse.Message = 'Processing....'
  # summarize all documents in the target category,
  # and save the results into a separate bucket.
  # We do not need typesense to process entire documents for indexing and document generation.
  # We need to reduce the amount of data that is bing processed by Typesense.
  newDocumentBucketName = f'{bucketRootName}-new'
  if not await minioObject.BucketExists(newDocumentBucketName):
    currentResponse.Message = (
      f'No bucket with name: {newDocumentBucketName} found.'
    )
    currentResponse.Finished = True
    yield serverResponse.GenerateServerResponse(
      currentResponse,
      className=__name__,
      errorType=ErrorTypes.Error,
    )
    return

  # send off the number of documents in the bucket.
  documentCount = minioObject.GetNumberOfObjectsInBucket(newDocumentBucketName)
  currentResponse.Data['document_count'] = documentCount
  yield serverResponse.GenerateServerResponse(currentResponse)

  uploadedDocumentNames = []
  unprocessedDocumentNames = []
  mergedContent = ''
  # Get all original documents in the storage bucket.
  for document in minioObject.GetObjectsInBucket(newDocumentBucketName):
    currentResponse.Message = 'Processing...'
    currentResponse.Data['processed_document_count'] = len(
      uploadedDocumentNames
    ) + len(unprocessedDocumentNames)
    yield serverResponse.GenerateServerResponse(currentResponse)

    # For each document, generate summarized document
    if document.object_name is None:
      serverResponse.GenerateLogMessage(
        messageString=f'Tried to process a document with no name from bucket: {newDocumentBucketName}, skipping file.'
      )
      unprocessedDocumentNames.append(document.object_name)
      continue
    result = minioObject.GetContentOfBucketObject(
      newDocumentBucketName, document.object_name
    )
    if not result.Success:
      serverResponse.GenerateLogMessage(
        messageString=f'Failed to get content from file: {document.object_name.split(".")[0]}, from bucket: {newDocumentBucketName}, skipping file.'
      )
      unprocessedDocumentNames.append(document.object_name)
      continue
    originalContent = result.Data['content']
    summarizedDocumentContent = await SummarizeDocument(
      content=originalContent,
      context=f'folder name: {bucketRootName}, file name:{document.object_name}',
      llmObject=llmObject,
    )
    keySummarizedContent = await SummarizeToKeyIdentifiers(
      content=originalContent,
      context=f'folder name: {bucketRootName}, file name:{document.object_name}',
      llmObject=llmObject,
    )
    summarizedDocumentContent.extend(keySummarizedContent)
    print(f'summarizedContent: {summarizedDocumentContent}')

    # Upload summarized document into their own bucket and store a reference in the database table.
    # story both the original document path and the summarized document path.
    summarizedDocumentName = (
      f'{document.object_name.split(".")[0]}-summarized.txt'
    )
    summarizedBucketName = f'{bucketRootName}-summarized'
    result = await UploadProcessedDocuments(
      f'{bucketRootName}-processed',
      summarizedBucketName,
      originalContent,
      json.dumps(summarizedDocumentContent, indent=0),
      f'{document.object_name.split(".")[0]}-processed.txt',
      summarizedDocumentName,
      serverResponse=serverResponse,
      minioObject=minioObject,
      postgresObject=postgresObject,
    )
    if not result.Success:
      serverResponse.GenerateLogMessage(
        messageString=f'failed to upload: {document.object_name}, skipping file.'
      )
      unprocessedDocumentNames.append(document.object_name)
      continue
    serverResponse.GenerateLogMessage(
      messageString=f'document: {document.object_name} has been processed successfully.'
    )
    uploadedDocumentNames.append(document.object_name)

    # move the document from the new bucket to the processed bucket
    minioObject.DeleteDocument(document.object_name, newDocumentBucketName)
    mergedContent += f'\n {json.dumps(summarizedDocumentContent, indent=0)}'

  currentResponse.Success = len(uploadedDocumentNames) > 0
  currentResponse.Message = (
    f'finished uploading {len(uploadedDocumentNames)} documents'
  )
  currentResponse.Data['DocumentNames'] = uploadedDocumentNames
  currentResponse.Data['document_count'] = documentCount
  currentResponse.Data['processed_document_count'] = len(
    uploadedDocumentNames
  ) + len(unprocessedDocumentNames)
  currentResponse.Finished = True
  yield serverResponse.GenerateServerResponse(currentResponse)


async def SummarizeToKeyIdentifiers(
  content: str,
  context: str,
  llmObject: LLM_Object,
):
  """
  Focuses on summarizing the document to detect names, key items, or people
  Args:
      content: str : The content to be summarized
      context: str : The context used to guide the LLM when summarizing the document.
      llmObject: LLM_Object : the llm object that will be used to summarize the document.
  """
  summarizedContent = []
  for paragraph in content.split('\n\n'):
    if len(paragraph) <= 0:
      continue
    llmResponse = await llmObject.Generate(
      f"""paragraph: {paragraph} \nUse the following context: {context}: identify key items, people, names, statistics, or figures from the paragraph into a JSON list of {{"topic": "topic name", "quote":"quote from paragraph"}}. Respond with only valid JSON."""
    )
    if not llmResponse.Success:
      continue
    # strip and process into json
    llmResponse = json.loads(
      JsonUtils.TryConvertStringToJson(llmResponse.Response)
    )
    for match in llmResponse['matches']:
      try:
        summarizedContent.append(
          {'topic': match['topic'], 'quote': match['quote']}
        )
      except Exception:
        pass

  return summarizedContent


async def SummarizeDocument(
  content: str,
  context: str,
  llmObject: LLM_Object,
):
  """
  Summarizes the given content's paragraphs content by the resolution
  For example if a resolution of 2 is given, then each paragraph of the content will be summarized twice.

  Args:
      content: str : The content to be summarized
      context: str : The context used to guide the LLM when summarizing the document.
      llmObject: LLM_Object : the llm object that will be used to summarize the document.
  """
  summarizedContent = []
  for paragraph in content.split('\n\n'):
    if len(paragraph) <= 0:
      continue
    # summarizedParagraph = await llmObject.GenerateV2(
    #   f"""paragraph: {paragraph} \n summarize the paragraph into 75% of its original length using the context: {context}. Only reply with the summarized content and do not write anything else or respond to this prompt."""
    # )
    llmResponse = await llmObject.Generate(
      f"""paragraph: {paragraph} \nUse the following context: {context}: To summarize and format the paragraph into a JSON list of {{"topic": "topic name", "quote":"quote from paragraph"}}. Respond with only valid JSON."""
    )
    if not llmResponse.Success:
      continue
    # strip and process into json
    llmResponse = json.loads(
      JsonUtils.TryConvertStringToJson(llmResponse.Response)
    )
    for match in llmResponse['matches']:
      try:
        summarizedContent.append(
          {'topic': match['topic'], 'quote': match['quote']}
        )
      except Exception:
        pass

  return summarizedContent


async def UploadProcessedDocuments(
  originalBucketName: str,
  summarizedBucketName: str,
  originalContent: str,
  summarizedContent: str,
  originalFileName: str,
  summarizedFileName: str,
  serverResponse: ServerResponse,
  minioObject: MinIO_Object,
  postgresObject: Postgres_Object,
) -> ServerResponseObject:
  """Uploads the summarized document to bucket and stores the summarized and original reference in the database"""
  # Upload original file to the storage server.
  result = minioObject.UploadDocumentToStorageServer(
    originalBucketName, originalContent, originalFileName
  )
  if not result.Success:
    return result
  # Upload summarized file to the storage server.
  result = minioObject.UploadDocumentToStorageServer(
    summarizedBucketName, summarizedContent, summarizedFileName
  )
  if not result.Success:
    return result

  # Upload the file name to our referencing database
  result = await postgresObject.RegisterDocument(
    f'summarizedDocumentReference_{summarizedBucketName}',
    f'{originalBucketName}/{originalFileName}',
    f'{summarizedBucketName}/{summarizedFileName}',
  )
  if not result.Success:
    return result

  # document upload complete
  result.Success = True
  result.Message = 'Summarized document upload complete.'
  return serverResponse.GenerateServerResponse(result)
