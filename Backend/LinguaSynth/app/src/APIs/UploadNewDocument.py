from Utils.ServerResponse import ServerResponseObject
from fastapi import UploadFile
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponse

DATABASE_NAME = 'raw-database'


class Uploader:
  def __init__(
    self, minio: MinIO_Object, serverResponse: ServerResponse
  ) -> None:
    self.minio = minio
    self.serverResponse = serverResponse

  async def UploadNewDocument(
    self,
    file: UploadFile,
  ) -> ServerResponseObject:
    """Uploads the document to the storage location for new documents, used before processing"""
    currentResponse = ServerResponseObject()
    content = (await file.read()).decode('utf-8')

    validation = self.__Validation(content, file.filename)  # type: ignore
    currentResponse.Message = validation[0]
    if not validation[1]:
      return self.serverResponse.GenerateServerResponse(currentResponse)

    result = await self.__UploadDocument(content, file.filename)  # type: ignore
    if not result.Success:
      currentResponse.Message = (
        f'failed to upload file for reason: {result.Message}'
      )

    currentResponse.Success = True
    currentResponse.Data = {'result': result}
    currentResponse.Finished = True
    return self.serverResponse.GenerateServerResponse(currentResponse)

  def __Validation(self, content: str, fileName: str):
    if fileName is None or fileName == '.txt':
      return 'File has no name', False
    if content == '':
      return 'File content is empty.', False

    return f'New document: {fileName} uploaded to bucket: {DATABASE_NAME}', True

  async def __UploadDocument(self, content: str, fileName: str):
    return self.minio.UploadDocumentToStorageServer(
      bucketName=DATABASE_NAME,
      content=content,
      documentName=fileName,
    )
