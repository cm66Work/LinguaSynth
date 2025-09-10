from fastapi import FastAPI, UploadFile, File  # pyright: ignore[reportAssignmentType]
from secrets import token_hex
import os
from MinIOManager import MinIOManager
from PostgresManager import PostgresManager

# --- Constants ---
UPLOAD_BUCKET_NAME = 'upload'

# --- Minio ---
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
minioManager = MinIOManager(username, password, address, port)

# --- API ---
app = FastAPI()

# --- Postgres ---
address = os.getenv('POSTGRES_ADDRESS', 'db')
port = os.getenv('POSTGRES_PORT', '5432')
databaseName = os.getenv('POSTGRES_DB', 'test_db')

# using the file so we need to read the contents
username = os.getenv('POSTGRES_USER_FILE', 'test_user')
password = os.getenv('POSTGRES_PASSWORD_FILE', 'test_password')
# only update username and password if we had read a file path and not the default minio credentials
# just in case we pass them instead of the actual files
if not username == 'test_user' or password == 'test_password':
  with open(username) as f:
    username = f.read()
  with open(password) as f:
    password = f.read()
postgresManager = PostgresManager(username, password, address, port, databaseName)


# --- Code ---
@app.get('/')
async def root():
  return {'message:': 'Hello World!'}


@app.get('/healthcheck')
async def HealthCheck():
  return {'message': 'Healthy'}


@app.post('/uploadfile/')
async def UploadFile(file: UploadFile = File(...)):  # pyright: ignore[reportGeneralTypeIssues]
  uploadResult = await HandleSummarizedFileGeneration(file)
  # TODO:: Store the path to both the summarized file and the original file inside database
  # TODO:: Pass the summarized file into Typesense
  return {
    'success': True,
    'filePath': '',
    'message': 'File uploaded successfully.',
  }


# --- Handlers ---
async def HandleSummarizedFileGeneration(file: UploadFile = File(...)):  # type: ignore
  # TODO:: Get or generate the schema
  # TODO:: Create a temp file
  filename = file.filename
  filename = f'{filename.split(".")[0]}-summarized.{filename.split(".")[1]}'
  content = await file.read()
  if not minioManager.BucketExists(UPLOAD_BUCKET_NAME):
    minioManager.CreateBucket(UPLOAD_BUCKET_NAME)
  return minioManager.UploadFileContents(UPLOAD_BUCKET_NAME, filename, content)

  # TODO:: Use LLM to summarize temp file using schema
  # TODO:: upload the summarized file to Minio
