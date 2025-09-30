import requests
import json


class ProcessUploadedDocuments:
  def __init__(self, serverAddress, category, progressBarCallback=None):
    self.serverAddress = serverAddress
    self.category = category
    self.progressBarCallback = progressBarCallback

  def ProcessFiles(self):
    """Tells the server to start processing all new uploaded documents and streams back progress."""
    with requests.post(
      f'{self.serverAddress}/process-new-uploaded-documents/?bucketRootName={self.category}',
      stream=True,
    ) as response:
      if response.status_code != 200:
        return None, response.status_code

      # Iterate over streamed lines
      for line in response.iter_lines():
        if line:
          try:
            data = json.loads(line.decode('utf-8'))
            print('Stream update:', data)

            # Notify GUI for progress
            if self.progressBarCallback:
              currentProgress = data['Data'].get('processed_document_count', 0)
              totalDocumentsCount = data['Data'].get('document_count', 100)
              self.progressBarCallback(currentProgress, totalDocumentsCount)
          except json.JSONDecodeError:
            print('Invalid JSON chunk:', line)

      return 'Completed', response.status_code
