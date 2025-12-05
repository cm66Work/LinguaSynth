from Utils.ServerResponse import ServerResponseObject
from fastapi import UploadFile
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2


class Uploader:
  def __init__(
    self, minio: MinIO_Object, serverResponse: ServerResponseV2, bucketName: str
  ) -> None:
    self.minio = minio
    self.serverResponse = serverResponse
    self.bucketName = bucketName

  async def UploadDocumentContentAsFile(self, content: str, fileName: str):
    return self.minio.UploadDocumentToStorageServer(
      bucketName=self.bucketName,
      content=content,
      documentName=fileName,
    )

  async def UploadNewFile(
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

    result = await self.UploadDocumentContentAsFile(content, file.filename)  # type: ignore
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

    return (
      f'New document: {fileName} uploaded to bucket: {self.bucketName}',
      True,
    )
