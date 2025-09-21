import os
from Managers.PostgresManager import PostgresManager


# --- Constants ---
DB_TABLE_NAME = 'file_reference_table'
DB_TABLE_COLUMNS = {
  'id': 'SERIAL PRIMARY KEY',
  'originalFilePath': 'TEXT NOT NULL',
  'summarizedFilePath': 'TEXT NOT NULL',
}


class Postgres_Object:
  def __init__(self):
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
    self.client = PostgresManager(username, password, address, port, databaseName)

  async def UploadFilePathsToDataBase(self, originalFilePath, summarizedFilePath):
    """
    Creates a entry containing both the original and summarized file paths,
    so they can be referenced later.

    Args:
        originalFilePath (str): path to the original file storage location.
        summarizedFilePath (str): path to the summarized file storage location.
    """
    if not self.client.TableExists(DB_TABLE_NAME).Success:
      self.client.CreateTable(DB_TABLE_NAME, DB_TABLE_COLUMNS)
    data = {
      'originalFilePath': originalFilePath,
      'summarizedFilePath': summarizedFilePath,
    }
    return self.client.InsertIntoTable(DB_TABLE_NAME, data)
