import os
import pytest
from minio.error import S3Error
from MinIOManager import MinIOManager

# --- Configuration ---
BUCKET_NAME = 'test-bucket'
TEST_FILE_NAME = 'hello.txt'
FILE_CONTENT = b'Hello, MinIO!'


@pytest.fixture(scope='module')
def Manager():
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
  return MinIOManager(username, password, address, port)


# --- Bucket Tests ---
def test_create_bucket_when_not_exists(Manager):
  Manager.PurgeBucket(BUCKET_NAME)
  assert Manager.CreateBucket(BUCKET_NAME)


def test_create_bucket_when_exists(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  with pytest.raises(S3Error):
    Manager.CreateBucket(BUCKET_NAME)


# --- Upload Tests ---
def test_upload_object_when_not_exists(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  response = Manager.UploadFileContents(BUCKET_NAME, TEST_FILE_NAME, FILE_CONTENT)
  assert response['success']


def test_upload_object_when_exists(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  Manager.UploadFileContents(BUCKET_NAME, TEST_FILE_NAME, FILE_CONTENT)
  # Uploading again should overwrite without error
  response = Manager.UploadFileContents(BUCKET_NAME, TEST_FILE_NAME, FILE_CONTENT)
  assert response['success']


# --- Download Tests ---
def test_download_object_when_exists(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  Manager.UploadFileContents(BUCKET_NAME, TEST_FILE_NAME, FILE_CONTENT)
  response = Manager.DownloadFileContentFromBucket(BUCKET_NAME, TEST_FILE_NAME)
  print(f'response: {response}')
  assert response == FILE_CONTENT


def test_download_object_when_not_exists(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  if Manager.FileExistsInBucket(BUCKET_NAME, TEST_FILE_NAME):
    Manager.DeleteFileFromBucket(BUCKET_NAME, TEST_FILE_NAME)
  response = Manager.DownloadFileContentFromBucket(BUCKET_NAME, TEST_FILE_NAME)
  assert len(response) <= 0


# --- Delete Object Tests ---
def test_delete_object_when_exists(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  if not Manager.FileExistsInBucket(BUCKET_NAME, TEST_FILE_NAME):
    Manager.UploadFileContents(BUCKET_NAME, TEST_FILE_NAME, FILE_CONTENT)
  assert Manager.DeleteFileFromBucket(BUCKET_NAME, TEST_FILE_NAME)


def test_delete_object_when_not_exists(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  assert not Manager.DeleteFileFromBucket(BUCKET_NAME, TEST_FILE_NAME)


# --- Delete Bucket Tests ---
def test_delete_bucket_when_exists(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  bucketsCountBefore = len(Manager.GetAllBuckets())
  assert Manager.RemoveBucket(BUCKET_NAME)
  bucketsCountAfter = len(Manager.GetAllBuckets())
  # check to see if we deleted more than 1 bucket by mistake.
  assert (bucketsCountBefore - bucketsCountAfter) == 1


def test_delete_bucket_when_not_exists(Manager):
  if Manager.BucketExists(BUCKET_NAME):
    Manager.RemoveBucket(BUCKET_NAME)
  assert not Manager.RemoveBucket(BUCKET_NAME)


def test_delete_bucket_when_exists_and_object_inside(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  if len(list(Manager.GetAllObjectsInBucket(BUCKET_NAME))) <= 0:
    Manager.UploadFileContents(BUCKET_NAME, TEST_FILE_NAME, FILE_CONTENT)
  assert not Manager.RemoveBucket(BUCKET_NAME)


# --- Purge Bucket Tests ---
def test_purge_bucket_when_exists(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  bucketsCountBefore = len(Manager.GetAllBuckets())
  assert Manager.PurgeBucket(BUCKET_NAME)
  bucketsCountAfter = len(Manager.GetAllBuckets())
  # check to see if we deleted more than 1 bucket by mistake.
  assert (bucketsCountBefore - bucketsCountAfter) == 1


def test_purge_bucket_when_not_exists(Manager):
  if Manager.BucketExists(BUCKET_NAME):
    Manager.PurgeBucket(BUCKET_NAME)
  assert not Manager.RemoveBucket(BUCKET_NAME)


def test_purge_bucket_when_exists_and_object_inside(Manager):
  if not Manager.BucketExists(BUCKET_NAME):
    Manager.CreateBucket(BUCKET_NAME)
  if len(list(Manager.GetAllObjectsInBucket(BUCKET_NAME))) <= 0:
    Manager.UploadFileContents(BUCKET_NAME, TEST_FILE_NAME, FILE_CONTENT)
  assert Manager.PurgeBucket(BUCKET_NAME)
