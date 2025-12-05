from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject


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
