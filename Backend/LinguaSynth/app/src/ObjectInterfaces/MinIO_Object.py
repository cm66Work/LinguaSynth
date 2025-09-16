from typing import Any
import os
from Managers.MinIOManager import MinIOManager
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

  async def UploadNewFileToBucket(
    self, fileName: str, originalContent: str, summarizedContent: str
  ) -> dict[str, Any]:
    """
    Saves two copies of the same file, one summarized and one original to
    the minio bucket.

    Args:
        fileName (str): The name of the original file.
        originalContent (str): The original content of the file.
        summarizedContent (str): The summarized version of the original content.
    Returns:
    """
    if not self.client.BucketExists(UPLOAD_ORIGINAL_BUCKET_NAME):
      self.client.CreateBucket(UPLOAD_ORIGINAL_BUCKET_NAME)
    originalResult = self.___UploadContentToTargetBucket(
      UPLOAD_ORIGINAL_BUCKET_NAME, fileName, originalContent
    )

    filename = f'{fileName.split(".")[0]}-summarized.{fileName.split(".")[1]}'
    if not self.client.BucketExists(UPLOAD_SUMMARIZED_BUCKET_NAME):
      self.client.CreateBucket(UPLOAD_SUMMARIZED_BUCKET_NAME)
    summaryResult = self.___UploadContentToTargetBucket(
      UPLOAD_SUMMARIZED_BUCKET_NAME, filename, summarizedContent
    )

    return {'originalFile': originalResult, 'summarizedFile': summaryResult}

  def ___UploadContentToTargetBucket(
    self, bucketName: str, fileName: str, content: str
  ) -> ServerResponseObject:
    return self.client.UploadFileContents(bucketName, fileName, content)

  async def GetSchemaContent(self):
    return str(self.client.DownloadFileContentFromBucket('schema', SCHEMA_FILE_NAME))

  def UploadSchema(self, content: str):
    if not self.client.BucketExists(UPLOAD_SCHEMA_BUCKET_NAME):
      self.client.CreateBucket(UPLOAD_SCHEMA_BUCKET_NAME)
    return self.___UploadContentToTargetBucket(
      UPLOAD_SCHEMA_BUCKET_NAME, SCHEMA_FILE_NAME, content
    )
