import os
from src.Managers.TypesenseManager import TypesenseManager
import pytest

# --- Constants ---
TEST_COLLECTION = 'document_test'


@pytest.fixture(scope='session')
def schema():
  return {
    'name': TEST_COLLECTION,
    'fields': [
      {'name': 'id', 'type': 'string'},
      {'name': 'name', 'type': 'string'},
      {'name': 'content', 'type': 'string'},
    ],
  }


@pytest.fixture
def documents():
  return [
    {'id': '1', 'name': 'doc_alpha', 'content': 'The sky is blue and clear.'},
    {'id': '2', 'name': 'doc_beta', 'content': 'The ocean is vast and deep.'},
    {'id': '3', 'name': 'doc_beta1', 'content': 'The ocean is vast and deep.'},
    {'id': '4', 'name': 'doc_beta2', 'content': 'The ocean is vast and deep.'},
    {'id': '5', 'name': 'doc_beta3', 'content': 'The ocean is vast and deep.'},
    {'id': '6', 'name': 'doc_beta4', 'content': 'The ocean is vast and deep.'},
    {'id': '7', 'name': 'doc_beta5', 'content': 'The ocean is vast and deep.'},
    {'id': '8', 'name': 'doc_beta6', 'content': 'The ocean is vast and deep.'},
    {'id': '9', 'name': 'doc_gamma', 'content': 'Mountains are tall and majestic.'},
  ]


@pytest.fixture(scope='module')
def Manager():
  return TypesenseManager(
    host=os.getenv('TYPESENSE_HOST', 'typesense'),
    port=os.getenv('TYPESENSE_PORT', '8108'),
    protocol=os.getenv('TYPESENSE_PROTOCOL', 'http'),
    apiKey=os.getenv('TYPESENSE_API_KEY', 'xyz'),
    searchApiKey=os.getenv('TYPESENSE_SEARCH_API_KEY', 'xyz'),
  )


# region Collection tests
def test_create_collection(Manager, schema):
  result = Manager.RecreateCollection(schema, True)
  assert result.Success


def test_file_indexing_and_searching(Manager, documents, schema):
  result = Manager.RecreateCollection(schema, True)
  assert result.Success
  response = Manager.IndexDocuments(schema['name'], documents)
  assert response.Success  # will be true if all files are indexed correctly.
  response = Manager.NewQuery(TEST_COLLECTION, 'ocean')
  assert response.Success


def test_search_with_few_result_case(Manager, documents, schema):
  result = Manager.RecreateCollection(schema, True)
  assert result.Success
  response = Manager.IndexDocuments(schema['name'], documents)
  assert response.Success  # will be true if all files are indexed correctly.
  response = Manager.NewQuery(TEST_COLLECTION, 'sky')
  assert response.Success
  print(response)
  assert response.Data['confidence'] == -1
  assert len(response.Data['documents']) == 1  # documents with the word sky in it.


def test_search_with_many_results_case(Manager, documents, schema):
  result = Manager.RecreateCollection(schema, True)
  assert result.Success
  response = Manager.IndexDocuments(schema['name'], documents)
  assert response.Success  # will be true if all files are indexed correctly.
  response = Manager.NewQuery(TEST_COLLECTION, 'ocean', maxHits=3)
  assert response.Success
  print(response)
  assert response.Data['confidence'] == 0
  assert len(response.Data['documents']) == 7  # documents with the word ocean in it.


# endregion
