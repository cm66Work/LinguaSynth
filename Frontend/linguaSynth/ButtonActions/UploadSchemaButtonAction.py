import json
import requests


class UploadSchemaButtonAction:
  def __init__(
    self,
    serverAddress,
    categoryName,
    schemaJsonString: str,
    progressbarCallback,
    force: bool = False,
  ) -> None:
    self.serverAddress = serverAddress
    self.categoryName = categoryName
    self.schemaJsonString = schemaJsonString
    self.progressBarCallback = progressbarCallback
    self.force = force

  def UploadSchema(self):
    # TODO:: Fixed this by adding a button to toggle force.
    self.force = True
    with requests.post(
      f'{self.serverAddress}/upload-schema/?schemaName={self.categoryName}&schema={self.schemaJsonString}&force={self.force}',
      stream=True,
    ) as response:
      if response.status_code != 200:
        return None, response.status_code

      # Iterate over streamed lines
      success = False
      for line in response.iter_lines():
        if line:
          try:
            data = json.loads(line.decode('utf-8'))

            # Notify GUI for progress
            if self.progressBarCallback:
              if not bool(data['Success']):
                self.progressBarCallback(0, 100, 'Uploading...')
              else:
                self.progressBarCallback(100, 100, 'Finished')
                if bool(data['Success']):
                  success = True
          except json.JSONDecodeError:
            print('Invalid JSON chunk:', line)

      return success, response.status_code
