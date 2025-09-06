from fastapi import FastAPI, UploadFile, File  # pyright: ignore[reportAssignmentType]
from secrets import token_hex
import os
from MinIOManager import MinIOManager


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


app = FastAPI()


@app.get('/')
async def root():
  return {'message:': 'Hello World!'}


@app.get('/healthcheck')
async def HealthCheck():
  return {'message': 'Healthy'}


@app.post('/uploadfile/')
async def UploadFile(bucketName: str, file: UploadFile = File(...)):  # pyright: ignore[reportGeneralTypeIssues]
  fileExtension = file.filename.split('.').pop()  # eg: png, jpeg, txt, etc....
  # encrypt the file name before upload.
  fileName = token_hex(10)
  filePath = f'{fileName}.{fileExtension}'
  content = await file.read()
  if not minioManager.BucketExists(bucketName):
    minioManager.CreateBucket(bucketName)
  minioManager.UploadFileContents(bucketName, filePath, content)
  return {'success': True, 'filePath': filePath, 'message': 'File uploaded successfully.'}
