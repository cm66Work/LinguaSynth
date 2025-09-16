import os
from src.Managers.TypesenseManager import TypesenseManager
import pytest

# --- Constants ---
TYPESENSE_HOST = os.getenv('TYPESENSE_HOST', 'typesense')
TYPESENSE_PORT = os.getenv('TYPESENSE_PORT', '8108')
TYPESENSE_PROTOCOL = os.getenv('TYPESENSE_PROTOCOL', 'http')
TYPESENSE_SEARCH_API_KEY = os.getenv('TYPESENSE_SEARCH_KEY', 'xyz')
TYPESENSE_API_KEY = os.getenv('TYPESENSE_API_KEY', 'xyz')

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
    'default_sorting_field': 'id',
  }


@pytest.fixture
def documents():
  return [
    {'id': '1', 'name': 'doc_alpha', 'content': 'The sky is blue and clear.'},
    {'id': '2', 'name': 'doc_beta', 'content': 'The ocean is vast and deep.'},
    {'id': '3', 'name': 'doc_gamma', 'content': 'Mountains are tall and majestic.'},
  ]


@pytest.fixture(scope='module')
def Manager(schema):
  return TypesenseManager(
    host=TYPESENSE_HOST,
    port=TYPESENSE_PORT,
    protocol=TYPESENSE_PROTOCOL,
    apiKey=TYPESENSE_API_KEY,
    searchApiKey=TYPESENSE_SEARCH_API_KEY,
  )


# --- Tests ---
def test_create_collection(Manager):
  result = Manager.RecreateCollection(schema, TEST_COLLECTION)
  assert result.Success


def test_file_indexing_and_searching(Manager, documents):
  result = Manager.RecreateCollection(schema, TEST_COLLECTION)
  assert result.Success

  response = Manager.IndexDocuments(TEST_COLLECTION, documents)
  assert response.Success  # will be true if all files are indexed correctly.
  response = Manager.NewQuery(TEST_COLLECTION, 'ocean')
  assert response.Success
  assert len(response.Data['documents']) > 0


# def test_search_with_few_result_case(manager, load_documents):
#   pass


# def test_search_with_many_results_case(manager, schema):
#   pass
