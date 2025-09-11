import os
import pytest
from PostgresManager import PostgresManager


# --- Configuration ---
TABLE_NAME = 'test_table'
TABLE_COLUMNS = {
  'id': 'SERIAL PRIMARY KEY',
  'originalFilePath': 'TEXT NOT NULL',
  'summarizedFilePath': 'TEXT NOT NULL',
}
"""
Primary use case would be to have a table with a primary key and two
text file path entries, so we are only going to build test cases for these,
as building test cases for anything else would be out of scope at this moment.
"""


# --- Fixtures ---
@pytest.fixture(scope='module')
def Manager():
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
  return PostgresManager(username, password, address, port, databaseName)


# --- Table creation ---
def test_create_table_success(Manager):
  if Manager.TableExists(TABLE_NAME)['success']:
    Manager.PurgeTable(TABLE_NAME)
  assert Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)['success']


def test_create_table_already_exists(Manager):
  if Manager.TableExists(TABLE_NAME)['success']:
    Manager.PurgeTable(TABLE_NAME)
  assert Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)['success']
  assert not Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)['success']


# --- Table deletion ---
def test_drop_table_success(Manager):
  if not Manager.TableExists(TABLE_NAME)['success']:
    Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)
  assert Manager.PurgeTable(TABLE_NAME)['success']


def test_drop_table_not_exists(Manager):
  if Manager.TableExists(TABLE_NAME)['success']:
    Manager.PurgeTable(TABLE_NAME)
  assert not Manager.PurgeTable(TABLE_NAME)['success']


# --- Insert entry ---
def test_insert_entry_success(Manager):
  if not Manager.TableExists(TABLE_NAME)['success']:
    Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)

  data = {
    'originalFilePath': 'originalFile.txt',
    'summarizedFilePath': 'summarizedFile.txt',
  }
  assert Manager.InsertIntoTable(TABLE_NAME, data)['success']


def test_insert_entry_table_not_exists(Manager):
  if Manager.TableExists(TABLE_NAME)['success']:
    Manager.PurgeTable(TABLE_NAME)

  data = {
    'originalFilePath': 'originalFile.txt',
    'summarizedFilePath': 'summarizedFile.txt',
  }
  assert not Manager.InsertIntoTable(TABLE_NAME, data)['success']


# --- Delete entry ---
def test_delete_entry_success(Manager):
  if not Manager.TableExists(TABLE_NAME)['success']:
    Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)
  data = {
    'originalFilePath': 'originalFile.txt',
    'summarizedFilePath': 'summarizedFile.txt',
  }
  assert Manager.InsertIntoTable(TABLE_NAME, data)['success']
  assert Manager.DeleteEntry(TABLE_NAME, 'id', 1)['success']


def test_delete_entry_not_exists(Manager):
  if not Manager.TableExists(TABLE_NAME)['success']:
    Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)
  assert not Manager.DeleteEntry(TABLE_NAME, 'id', 1)['success']


# --- Table get all entries ---
def test_get_all_entries_when_entries_exist(Manager):
  if not Manager.TableExists(TABLE_NAME)['success']:
    Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)
  data = {
    'originalFilePath': 'originalFile.txt',
    'summarizedFilePath': 'summarizedFile.txt',
  }
  assert Manager.InsertIntoTable(TABLE_NAME, data)['success']
  assert Manager.InsertIntoTable(TABLE_NAME, data)['success']
  result = Manager.GetAllEntries(TABLE_NAME)
  assert result['success']
  assert len(result['data']['entries']) == 2


def test_get_all_entries_when_no_entries(Manager):
  if Manager.TableExists(TABLE_NAME)['success']:
    Manager.PurgeTable(TABLE_NAME)
  Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)
  result = Manager.GetAllEntries(TABLE_NAME)
  assert result['success']
  assert len(result['data']['entries']) == 0


def test_get_all_entries_when_no_Table_Exists(Manager):
  if Manager.TableExists(TABLE_NAME)['success']:
    Manager.PurgeTable(TABLE_NAME)
  result = Manager.GetAllEntries(TABLE_NAME)
  assert not result['success']
  assert len(result['data']['entries']) == 0


# --- Table get all entries ---
def test_get_entries_with_id_when_entries_exist(Manager):
  if Manager.TableExists(TABLE_NAME)['success']:
    Manager.PurgeTable(TABLE_NAME)
  Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)
  data = {
    'originalFilePath': 'originalFile.txt',
    'summarizedFilePath': 'summarizedFile.txt',
  }
  assert Manager.InsertIntoTable(TABLE_NAME, data)['success']
  assert Manager.InsertIntoTable(TABLE_NAME, data)['success']
  assert Manager.InsertIntoTable(TABLE_NAME, data)['success']
  result = Manager.GetEntryByID(TABLE_NAME, 2)
  assert result['success']
  assert len(result['data']['entries']) > 0
  assert result['data']['entries']['originalFilePath'] == data['originalFilePath']


def test_get_entries_with_id_when_entries_do_not_exist(Manager):
  if Manager.TableExists(TABLE_NAME)['success']:
    Manager.PurgeTable(TABLE_NAME)
  Manager.CreateTable(TABLE_NAME, TABLE_COLUMNS)
  data = {
    'originalFilePath': 'originalFile.txt',
    'summarizedFilePath': 'summarizedFile.txt',
  }
  assert Manager.InsertIntoTable(TABLE_NAME, data)['success']
  assert Manager.InsertIntoTable(TABLE_NAME, data)['success']
  result = Manager.GetEntryByID(TABLE_NAME, 3)
  assert not result['success']
  assert len(result['data']['entries']) == 0
  assert result['data']['entries'] == {}
