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
        return False, response.status_code

      # Iterate over streamed lines
      success = False
      for line in response.iter_lines():
        if line:
          try:
            data = json.loads(line.decode('utf-8'))
            # Notify GUI for progress
            if self.progressBarCallback:
              if not bool(data['Success']):
                self.progressBarCallback(
                  data['Data']['total_documents'],
                  data['Data']['processed_documents'],
                  'Indexing...',
                )
              else:
                self.progressBarCallback(100, 100, 'Finished')
                if bool(data['Success']):
                  success = True

          except json.JSONDecodeError:
            print('Invalid JSON chunk:', line)

      return success, response.status_code
