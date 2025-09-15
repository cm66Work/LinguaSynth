from LLMManager import LLMManager
from fastapi import FastAPI, UploadFile, File  # pyright: ignore[reportAssignmentType]
import os
from MinIOManager import MinIOManager
from PostgresManager import PostgresManager

# --- Constants ---
UPLOAD_ORIGINAL_BUCKET_NAME = 'original'
UPLOAD_SUMMARIZED_BUCKET_NAME = 'upload'
DB_TABLE_NAME = 'file_reference_table'
DB_TABLE_COLUMNS = {
  'id': 'SERIAL PRIMARY KEY',
  'originalFilePath': 'TEXT NOT NULL',
  'summarizedFilePath': 'TEXT NOT NULL',
}
LLM_LIGHT_GENERATION_MODEL = 'gemma3:1b-it-q8_0'
LLM_HEAVY_GENERATION_MODEL = 'gemma3:4b'


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


# --- Ollama ---
address = os.getenv('OLLAMA_ADDRESS', 'ollama')
llm = LLMManager(hostAddress=f'{address}:{port}', model=LLM_LIGHT_GENERATION_MODEL)


# --- APIs ---
@app.get('/')
async def root():
  return {'message:': 'Hello World!'}


@app.get('/healthcheck')
async def HealthCheck():
  return {'message': 'Healthy'}


@app.post('/uploadfile/')
async def UploadFile(file: UploadFile = File(...)):  # pyright: ignore[reportGeneralTypeIssues]
  uploadResult = await HandleSummarizedFileGeneration(file)
  if not uploadResult['summarizedFile']['success']:
    return {
      'success': False,
      'filePath': '',
      'message': 'ERROR::main:: Failed to upload file to Minio.',
    }
  summarizedFilePath = uploadResult['summarizedFile']['data']['file_path']

  originalFilePath = uploadResult['originalFile']['data']['file_path']
  await HandleDatabaseUploading(originalFilePath, summarizedFilePath)

  # TODO:: Pass the summarized file into Typesense
  return {
    'success': True,
    'filePath': f'{summarizedFilePath} : {originalFilePath}',
    'message': 'File uploaded successfully.',
  }


# --- Handlers ---
# --- File linking / referencing ---
async def HandleDatabaseUploading(originalFilePath: str, summarizedFilePath: str):
  """
  Creates a entry containing both the original and summarized file paths,
  so they can be referenced later.

  Args:
      originalFilePath (str): path to the original file storage location.
      summarizedFilePath (str): path to the summarized file storage location.
  """
  if not postgresManager.TableExists(DB_TABLE_NAME)['success']:
    postgresManager.CreateTable(DB_TABLE_NAME, DB_TABLE_COLUMNS)
  data = {'originalFilePath': originalFilePath, 'summarizedFilePath': summarizedFilePath}
  postgresManager.InsertIntoTable(DB_TABLE_NAME, data)


# --- File summarization ---
async def HandleSummarizedFileGeneration(file: UploadFile = File(...), schema={}):  # type: ignore
  """
  Summarizes The content of the given file using the provided schema.

  Args:
      file (File): The file that was uploaded through our api.
      schema (object): The schema used for file summarization.
  Returns:
      Returns an object containing both the original and summarized file objects.
  """
  filename = file.filename
  filename = f'{filename.split(".")[0]}-summarized.{filename.split(".")[1]}'
  # TODO:: Make cleaner when LLM is added
  content = await SummarizeFile(await file.read())
  # TODO:: this is a placeholder because we are not taking into consideration
  #        that the files will be stored on a different server from the server
  #        running LinguaSynth
  if not minioManager.BucketExists(UPLOAD_ORIGINAL_BUCKET_NAME):
    minioManager.CreateBucket(UPLOAD_ORIGINAL_BUCKET_NAME)
  originalResult = minioManager.UploadFileContents(
    UPLOAD_ORIGINAL_BUCKET_NAME, file.filename, await file.read()
  )

  if not minioManager.BucketExists(UPLOAD_SUMMARIZED_BUCKET_NAME):
    minioManager.CreateBucket(UPLOAD_SUMMARIZED_BUCKET_NAME)
  summaryResult = minioManager.UploadFileContents(
    UPLOAD_SUMMARIZED_BUCKET_NAME, filename, content
  )

  return {'originalFile': originalResult, 'summarizedFile': summaryResult}


async def SummarizeFile(content: str, schema: str):
  result = llm.Generate(
    model=LLM_LIGHT_GENERATION_MODEL,
    prompt=f'{schema} use the above schema to summarize the content in the following document: {content}',
  )
  return result
