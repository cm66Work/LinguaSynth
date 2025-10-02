from Utils.ServerResponse import ServerResponseObject
from fastapi import UploadFile
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponse


async def UploadNewDocument(
  documentCategory: str,
  file: UploadFile,
  minioObject: MinIO_Object,
  serverResponse: ServerResponse,
) -> ServerResponseObject:
  """Uploads the document to the storage location for new documents, used before processing"""
  content = (await file.read()).decode('utf-8')
  documentName = file.filename if file.filename is not None else 'tempt.txt'
  result = minioObject.UploadDocumentToStorageServer(
    bucketName=f'{documentCategory}-new', content=content, documentName=documentName
  )
  if not result.Success:
    return result

  return serverResponse.GenerateServerResponse(
    success=True,
    message=f'new document: {file.filename} uploaded.',
    extraData={'result': result},
  )
