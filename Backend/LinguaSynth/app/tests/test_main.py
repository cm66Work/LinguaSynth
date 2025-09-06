import pytest
import Utils.testUtils as testUtils
from fastapi.testclient import TestClient
from src.main import app



client = TestClient(app)

def test_basic():
  response = client.get("/healthcheck")
  testUtils.assert_message(response, 200, {"message": "Healthy"})