from Utils.DocumentHelpers import DocumentHelper
from APIs.UploadProcessedDocuments import UploadProcessedDocuments
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils.LogUtils import ErrorTypes


# region Document summarization and processing
# Process all original documents to summarized formats.
# is later used to indexing into Typesense.
async def ProcessNewDocuments(
  bucketRootName: str,
  serverResponse: ServerResponse,
  minioObject: MinIO_Object,
  postgresObject: Postgres_Object,
  frequencyThreshold: float = 0.25,
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

    # Upload summarized document into their own bucket and store a reference in the database table.
    # story both the original document path and the summarized document path.
    summarizedDocumentName = (
      f'{document.object_name.split(".")[0]}-summarized.txt'
    )
    summarizedBucketName = f'{bucketRootName}-summarized'

    # Extract the keywords form the current document.
    extractedKeywords = DocumentHelper.ExtractKeywords(
      originalContent, frequencyThreshold
    )
    result = await UploadProcessedDocuments(
      f'{bucketRootName}-processed',
      summarizedBucketName,
      originalContent,
      str(extractedKeywords)[1:-1].replace("'", ''),
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
