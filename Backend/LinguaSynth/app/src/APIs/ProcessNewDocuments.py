from dataclasses import asdict
import json

from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils.LogUtils import ErrorTypes
from fastapi.responses import StreamingResponse


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
) -> StreamingResponse:
  async def EventStream():
    yield (
      json.dumps(
        asdict(
          ServerResponseObject(
            Success=False, Message='Processing...', Data={'document_count': 1}
          )
        )
      )
      + '\n'
    )

    # summarize all documents in the target category,
    # and save the results into a separate bucket.
    # We do not need typesense to process entire documents for indexing and document generation.
    # We need to reduce the amount of data that is bing processed by Typesense.
    newDocumentBucketName = f'{bucketRootName}-new'
    if not await minioObject.BucketExists(newDocumentBucketName):
      yield json.dumps(
        asdict(
          serverResponse.GenerateServerResponse(
            success=False,
            message=f'No bucket with name: {newDocumentBucketName}',
            errorType=ErrorTypes.Error,
            className=__name__,
          )
        )
      )
      return

    # send off the number of documents in the bucket.
    documentCount = minioObject.GetNumberOfObjectsInBucket(newDocumentBucketName)
    yield (
      json.dumps(
        asdict(
          ServerResponseObject(
            Success=False,
            Message='Processing...',
            Data={'document_count': documentCount},
          )
        )
      )
      + '\n'
    )

    uploadedDocumentNames = []
    unprocessedDocumentNames = []
    mergedContent = ''
    # Get all original documents in the storage bucket.
    for document in minioObject.GetObjectsInBucket(newDocumentBucketName):
      yield (
        json.dumps(
          asdict(
            ServerResponseObject(
              Success=False,
              Message='Processing...',
              Data={
                'document_count': documentCount,
                'processed_document_count': len(uploadedDocumentNames)
                + len(unprocessedDocumentNames),
              },
            )
          )
        )
        + '\n'
      )
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
        context=f'{bucketRootName} and {document.object_name}',
        resolution=resolution,
        minioObject=minioObject,
        llmObject=llmObject,
      )
      if len(summarizedDocumentContent) <= 0:
        serverResponse.GenerateLogMessage(
          messageString=f'document: {document.object_name} summarized to nothing, skipping file.',
          errorType=ErrorTypes.Warning,
        )
        unprocessedDocumentNames.append(document.object_name)
        continue
      # Upload summarized document into their own bucket and store a reference in the database table.
      # story both the original document path and the summarized document path.
      summarizedDocumentName = f'{document.object_name.split(".")[0]}-summarized.txt'
      summarizedBucketName = f'{bucketRootName}-summarized'
      result = await UploadProcessedDocuments(
        f'{bucketRootName}-processed',
        summarizedBucketName,
        originalContent,
        summarizedDocumentContent,
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
      mergedContent += f'\n {summarizedDocumentContent}'

    yield json.dumps(
      asdict(
        serverResponse.GenerateServerResponse(
          success=len(uploadedDocumentNames) > 0,
          message=f'finished uploading {len(uploadedDocumentNames)} documents:',
          extraData={
            'DocumentNames': uploadedDocumentNames,
            'document_count': documentCount,
            'processed_document_count': len(uploadedDocumentNames)
            + len(unprocessedDocumentNames),
          },
          finished=True,
        )
      )
    )

    print('\n', mergedContent)

  return StreamingResponse(EventStream(), media_type='application/json')


async def SummarizeDocument(
  content: str,
  context: str,
  resolution: int,
  minioObject: MinIO_Object,
  llmObject: LLM_Object,
) -> str:
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
  # print(f'summarizedContent: {summarizedContent}')

  resolution -= 1
  if resolution > 0:
    return await SummarizeDocument(
      summarizedContent, context, resolution, minioObject, llmObject
    )
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
  return serverResponse.GenerateServerResponse(
    success=True,
    message='Summarized document Upload complete',
  )
