import os
import logging
from minio import Minio

class MinIOManager:
  def __init__(self, username="minioadmin", password="minioadmin", address="localhost", port="9000") -> None:
    self.username = username
    self.password = password
    self.address = address
    self.port = port

    # Logger
    self.logger = logging.getLogger(__name__)
    logging.basicConfig(filename="minio_logs", level=logging.INFO)
    self.logger.info("\n New Minio Log Started.................")

    # Create after we validate env 
    self.client = Minio(
        f"{self.address}:{self.port}",
        access_key=self.username,
        secret_key=self.password,
        secure=False
    )


  def CreateBucket(self, name):
    self.logger.info(f"Creating new bucket {name}...")
    self.client.make_bucket(name)
    return self.BucketExists(name)

  def BucketExists(self, name):
    return self.client.bucket_exists(name);

  def RemoveBucket(self, name):
    self.logger.info(f"Deleting bucket {name}...")
    if (self.BucketExists(name)):
      self.client.remove_bucket(name)


