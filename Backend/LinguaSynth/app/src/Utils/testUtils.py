# helper functions for testing

def assert_message(response, expectedStatusCode, expectedMessage):
  assert_status(response, expectedStatusCode)
  assert response.json() == expectedMessage, \
    f"Expected message:{expectedMessage}. Actual message: {response.json()}. Response text {response.text}"


def assert_status(response, expectedStatusCode=200): 
  assert response.status_code == expectedStatusCode, \
    f"Expected {expectedStatusCode}. Actual status {response.status_code}. Response text {response.text}"