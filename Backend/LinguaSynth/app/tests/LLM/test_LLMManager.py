import os
import pytest 
from src.LLMManager import LLMManager


# --- Fixtures ---
@pytest.fixture(scope='module')
def Manager():
  address = os.getenv('OLLAMA_ADDRESS', 'ollama')
  port = os.getenv('OLLAMA_PORT', '11434')

  return LLMManager(hostAddress=f'{address}:{port}', model='')


# --- Pulling Images ---
def test_pull_valid_model():
  # result = Manager.PullImage('gemma3:1b')
  # print(result)
  # assert result.Success
  pass


def test_pull_invalid_model():
  pass


def test_pull_valid_model_new():
  pass


def test_pull_valid_model_duplicate_model():
  pass


# -- Switching models ---
def test_switch_model_does_exist():
  pass


def test_switch_model_does_not_exist():
  pass


# --- Generating answers ---
def test_generate_response_with_prompt():
  pass


def test_generate_response_with_empty_prompt():
  pass


# --- Deleting models ---
def test_delete_model_does_exist():
  pass


def test_delete_model_does_not_exist():
  pass


# --- Get Models ---
def test_get_models_exists():
  pass


def test_get_models_empty():
  pass
