import io
import pytest
from minio.error import S3Error

from MinIOManager import MinIOManager
from minio import Minio 

BUCKET_NAME = "pytest-bucket"
TEST_FILE = "hello.txt"
LOCAL_FILE_CONTENT = "Hello, pytest with Minio!"


# @pytest.fixture(scope="module")
# def Manager():
#   return MinIOManager()
@pytest.fixture(scope="module")
def minio_client():
  return Minio(
  "localhost:9000", # Change if needed
  access_key="minioadmin",
  secret_key="minioadmin",
  secure=False,
  )
# --- Bucket Tests ---
# def test_create_bucket_when_not_exists(Manager):
#   # Manager.RemoveBucket(BUCKET_NAME)
#   assert Manager.CreateBucket(BUCKET_NAME)


# def test_create_bucket_when_exists(Manager):
#   if not Manager.BucketExists(BUCKET_NAME):
#     Manager.CreateBucket(BUCKET_NAME)
#   with pytest.raises(S3Error):
#     Manager.CreateBucket(BUCKET_NAME)

# --- Configuration ---
BUCKET_NAME = "test-bucket"
OBJECT_NAME = "hello.txt"
FILE_CONTENT = b"Hello, MinIO!"


# --- Bucket Tests ---
def test_create_bucket_when_not_exists(minio_client):
  if minio_client.bucket_exists(BUCKET_NAME):
    minio_client.remove_bucket(BUCKET_NAME)
  minio_client.make_bucket(BUCKET_NAME)
  assert minio_client.bucket_exists(BUCKET_NAME)


def test_create_bucket_when_exists(minio_client):
  if not minio_client.bucket_exists(BUCKET_NAME):
    minio_client.make_bucket(BUCKET_NAME)
  with pytest.raises(S3Error):
    minio_client.make_bucket(BUCKET_NAME)


# --- Upload Tests ---
def test_upload_object_when_not_exists(minio_client):
  if not minio_client.bucket_exists(BUCKET_NAME):
    minio_client.make_bucket(BUCKET_NAME)
  data = io.BytesIO(FILE_CONTENT)
  minio_client.put_object(BUCKET_NAME, OBJECT_NAME, data, len(FILE_CONTENT))
  stat = minio_client.stat_object(BUCKET_NAME, OBJECT_NAME)
  assert stat.size == len(FILE_CONTENT)


def test_upload_object_when_exists(minio_client):
  data = io.BytesIO(FILE_CONTENT)
  minio_client.put_object(BUCKET_NAME, OBJECT_NAME, data, len(FILE_CONTENT))
  # Uploading again should overwrite without error
  data2 = io.BytesIO(FILE_CONTENT)
  minio_client.put_object(BUCKET_NAME, OBJECT_NAME, data2, len(FILE_CONTENT))
  stat = minio_client.stat_object(BUCKET_NAME, OBJECT_NAME)
  assert stat.size == len(FILE_CONTENT)


# --- Download Tests ---
def test_download_object_when_exists(minio_client):
  response = minio_client.get_object(BUCKET_NAME, OBJECT_NAME)
  content = response.read()
  response.close()
  response.release_conn()
  assert content == FILE_CONTENT


def test_download_object_when_not_exists(minio_client):
  with pytest.raises(S3Error):
    minio_client.get_object(BUCKET_NAME, "doesnotexist.txt")


# --- Delete Object Tests ---
def test_delete_object_when_exists(minio_client):
  minio_client.remove_object(BUCKET_NAME, OBJECT_NAME)
  with pytest.raises(S3Error):
    minio_client.stat_object(BUCKET_NAME, OBJECT_NAME)


def test_delete_object_when_not_exists(minio_client):
  with pytest.raises(S3Error):
    minio_client.remove_object(BUCKET_NAME, "nonexistent.txt")


# --- Delete Bucket Tests ---
def test_delete_bucket_when_exists(minio_client):
  if not minio_client.bucket_exists(BUCKET_NAME):
    minio_client.make_bucket(BUCKET_NAME)
  minio_client.remove_bucket(BUCKET_NAME)
  assert not minio_client.bucket_exists(BUCKET_NAME)


def test_delete_bucket_when_not_exists(minio_client):
  if minio_client.bucket_exists(BUCKET_NAME):
    minio_client.remove_bucket(BUCKET_NAME)
  with pytest.raises(S3Error):
    minio_client.remove_bucket(BUCKET_NAME)