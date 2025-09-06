import io
import logging
from minio import Minio
import datetime


class MinIOManager:
  def __init__(
    self,
    username='minioadmin',
    password='minioadmin',
    address='localhost',
    port='9000',
    secure=False,
  ) -> None:
    self.username = username
    self.password = password
    self.address = address
    self.port = port

    # Logger
    self.logger = logging.getLogger(__name__)
    date = f'{datetime.datetime.now().strftime("%d")}'
    date += f'-{datetime.datetime.now().strftime("%m")}'
    date += f'-{datetime.datetime.now().strftime("%y")}'
    date += f'-{datetime.datetime.now().strftime("%H")}'
    date += f'-{datetime.datetime.now().strftime("%M")}'
    date += f'-{datetime.datetime.now().strftime("%S")}'
    date += '.txt'

    logging.basicConfig(filename=f'logs/minio/minio_logs:{date}', level=logging.INFO)
    self.logger.info('\n New Minio Log Started.................')

    # Create after we validate env
    self.client = Minio(
      f'{self.address}:{self.port}',
      access_key=self.username,
      secret_key=self.password,
      secure=False,
    )

  # ------------- Bucket Management
  def CreateBucket(self, name):
    """
    Creates a bucket
    """
    self.logger.info(f'Creating new bucket {name}...')
    self.client.make_bucket(name)
    return self.BucketExists(name)

  def BucketExists(self, name):
    """
    returns true if the bucket exists
    """
    return self.client.bucket_exists(name)

  def GetAllBuckets(self):
    return self.client.list_buckets()

  def PurgeBucket(self, name):
    """
    !!!WARNING!!! this is deleted everything inside the bucket.
    --- User RemoveBucket if you need to ensure bucket is empty before deleting it.
    Deletes the bucket BUT DOSE NOT CHECK FOR OBJECTS INSIDE IT
    Returns False if bucket does not exist.
    """
    self.logger.info(f'Purging bucket {name}...')
    if self.BucketExists(name):
      for fileObject in self.client.list_objects(name):
        self.DeleteFileFromBucket(name, fileObject.object_name)
      self.client.remove_bucket(name)
      return True
    return False

  def RemoveBucket(self, name):
    """
    Deleted the bucket but will return False if bucket has objects inside it
    or bucket does not exists.

    """
    self.logger.info(f'Deleting bucket {name}...')
    if self.BucketExists(name) and len(list(self.client.list_objects(name))) <= 0:
      self.client.remove_bucket(name)
      return True
    return False

  # ------------- File Management
  def FileExistsInBucket(self, bucketName, fileName):
    """
    Returns True if the files exists in the bucket.
    Returns False is ether the bucket or the files does not exist.
    """
    if not self.BucketExists(bucketName):
      return False
    bucketObjects = self.client.list_objects(bucketName)
    for bucketObjet in bucketObjects:
      if bucketObjet.object_name == fileName:
        return True
    return False

  def GetAllObjectsInBucket(self, bucketName):
    """
    Returns an iterator of Minio.Objects for all objects inside the bucket.
    """
    return self.client.list_objects(bucketName)

  def DeleteFileFromBucket(self, bucketName, fileName):
    """
    Deletes the file from the bucket if the bucket and the file exist.
    Returns False if bucket or file does not exist.
    """
    self.logger.info(f'Deleting file: {fileName} from bucket: {bucketName}...')
    if not self.FileExistsInBucket(bucketName, fileName):
      return False
    self.client.remove_object(bucketName, str(fileName))
    return True

  # ------------- File Uploading
  def UploadFileContents(self, bucketName, fileName, fileContents):
    """
    Uploads the given content to a bucket under the file name.
    Returns a FileUploadResponse dataClass after.
    """
    self.logger.info(f'Uploading file: {fileName} to bucket: {bucketName}...')
    if not self.BucketExists(bucketName):
      return None
    data = io.BytesIO(fileContents)
    self.client.put_object(bucketName, fileName, data, len(fileContents))
    stat = self.client.stat_object(bucketName, fileName)
    return stat

  # ------------- File Downloading
  def DownloadFileContentFromBucket(self, bucketName, fileName):
    """
    Returns the files content in the given bucket.
    Returns an empty string if bucket or file dose not exist.
    """
    self.logger.info(f'Downloading file: {fileName} from bucket: {bucketName}...')
    if not self.FileExistsInBucket(bucketName, fileName):
      return ''
    response = self.client.get_object(bucketName, fileName)
    content = response.read()
    response.close()
    return content
