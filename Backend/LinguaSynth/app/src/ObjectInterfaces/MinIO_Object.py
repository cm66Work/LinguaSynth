import os
from Managers.MinIOManager import (
  MinIOManager,
)
from Utils.ServerResponse import ServerResponseObject


UPLOAD_ORIGINAL_BUCKET_NAME = 'original'
UPLOAD_SUMMARIZED_BUCKET_NAME = 'summarized'
UPLOAD_SCHEMA_BUCKET_NAME = 'schema'
SCHEMA_FILE_NAME = 'schema.json'


class MinIO_Object:
  def __init__(self):
    address = os.getenv('MINIO_ADDRESS', 'minio')
    port = os.getenv('MINIO_API_PORT', '9000')

    # using the file so we need to read the contents
    username = os.getenv('MINIO_ROOT_USER_FILE', 'minioadmin')
    password = os.getenv('MINIO_ROOT_PASSWORD_FILE', 'minioadmin')
    # only update username and password if we had read a file path and not the default minio credentials
    # just in case we pass them instead of the actual files
    if not username == 'minioadmin' or password == 'minioadmin':
      with open(username) as f:
        username = f.read()
      with open(password) as f:
        password = f.read()
    self.client = MinIOManager(username, password, address, port)

  async def BucketExists(self, bucketName):
    return self.client.BucketExists(bucketName)

  def ___UploadContentToTargetBucket(
    self, bucketName: str, fileName: str, content: str
  ) -> ServerResponseObject:
    return self.client.UploadFileContents(bucketName, fileName, content)

  def UploadSchema(self, content: str, schemaName: str):
    if not self.client.BucketExists(UPLOAD_SCHEMA_BUCKET_NAME):
      self.client.CreateBucket(UPLOAD_SCHEMA_BUCKET_NAME)
    return self.___UploadContentToTargetBucket(
      UPLOAD_SCHEMA_BUCKET_NAME, f'{schemaName}-{SCHEMA_FILE_NAME}', content
    )

  def UploadDocumentToStorageServer(
    self, bucketName: str, content: str, documentName: str
  ):
    if not self.client.BucketExists(bucketName):
      self.client.CreateBucket(bucketName)
    return self.___UploadContentToTargetBucket(bucketName, f'{documentName}', content)

  def GetObjectsInBucket(self, bucketName: str):
    """Returns all documents inside the bucket if the bucket exists."""
    return self.client.GetAllObjectsInBucket(bucketName)

  def GetNumberOfObjectsInBucket(self, bucketName: str) -> int:
    """Returns the number of objects in the given bucket, returning 0 if bucket does not exist"""
    return self.client.GetObjectCountInBucket(bucketName)

  def GetContentOfBucketObject(
    self, bucketName: str, fileName: str
  ) -> ServerResponseObject:
    contentBytes = self.client.DownloadFileContentFromBucket(bucketName, fileName)

    if len(contentBytes) <= 0:
      return self.client.serverResponseUtil.GenerateServerResponse(
        success=False,
        message=f'failed to download content from file: {fileName}, in bucket: {bucketName}',
      )

    return self.client.serverResponseUtil.GenerateServerResponse(
      success=True,
      message=f'content downloaded from file: {fileName} in bucket: {bucketName}',
      extraData={'content': contentBytes.decode('utf-8')},
    )

  def DeleteDocument(self, documentName: str, bucketName: str) -> bool:
    result = self.client.DeleteFileFromBucket(bucketName, fileName=documentName)
    if self.GetNumberOfObjectsInBucket(bucketName) <= 0:
      self.client.PurgeBucket(bucketName)
    return result
