import json
import requests


class DocumentIndexingButtonAction:
  def __init__(
    self,
    serverAddress,
    categoryName,
    progressbarCallback,
  ) -> None:
    self.serverAddress = serverAddress
    self.categoryName = categoryName
    self.progressBarCallback = progressbarCallback

  def StartIndexingDocuments(self):
    with requests.post(
      f'{self.serverAddress}/start-indexing-documents/?schemaName={self.categoryName}'
    ) as response:
      if response.status_code != 200:
        return None, response.status_code

      # Iterate over streamed lines
      success = False
      for line in response.iter_lines():
        if line:
          try:
            data = json.loads(line.decode('utf-8'))
            print('Stream update:', data, '\n')

          except json.JSONDecodeError:
            print('Invalid JSON chunk:', line)

      return success, response.status_code
