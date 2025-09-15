import os
import pytest
from src.LLMManager import LLMManager


# --- Fixtures ---
@pytest.fixture(scope='session')
def existing_model():
  """Name of a known model available on Ollama Hub (e.g., mistral)."""
  return 'gemma3:1b-it-q8_0'


@pytest.fixture(scope='session')
def nonexistent_model():
  """Name of a model that should not exist."""
  return 'nonexistent-llm-xyz'


@pytest.fixture(scope='module')
def Manager():
  address = os.getenv('OLLAMA_ADDRESS', 'ollama')
  port = os.getenv('OLLAMA_PORT', '11434')

  return LLMManager(hostAddress=f'{address}:{port}', model='')


# --- Pulling Images ---
@pytest.mark.asyncio
async def test_pull_existing_mode(Manager, existing_model):
  result = await Manager.PullImage(existing_model)
  assert result.Success


@pytest.mark.asyncio
async def test_pull_none_existing_mode(Manager, nonexistent_model):
  result = await Manager.PullImage(nonexistent_model)
  assert not result.Success


# --- Generating answers --@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_generate_with_existing_model_and_prompt(Manager, existing_model):
  result = await Manager.Generate(existing_model, 'why is the sky blue?')
  assert result.Success


@pytest.mark.asyncio
async def test_generate_with_none_existing_model_and_prompt(Manager, nonexistent_model):
  result = await Manager.Generate(nonexistent_model, 'why is the sky blue?')
  assert not result.Success


@pytest.mark.asyncio
async def test_generate_with_existing_model_and_no_prompt(Manager, existing_model):
  result = await Manager.Generate(existing_model, '')
  assert not result.Success


@pytest.mark.asyncio
async def test_generate_with_none_existing_model_and_no_prompt(
  Manager, nonexistent_model
):
  result = await Manager.Generate(nonexistent_model, '')
  assert not result.Success
