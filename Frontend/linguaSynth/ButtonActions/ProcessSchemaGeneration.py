import requests
import json


class ProcessSchemaGeneration:
  def __init__(
    self,
    serverAddress,
    category,
    sampleSize,
    resolution,
    force=True,
    progressBarCallback=None,
  ):
    self.serverAddress = serverAddress
    self.category = category
    self.progressBarCallback = progressBarCallback
    self.sampleSize = sampleSize
    self.resolution = resolution
    self.force = force

  def GenerateSchema(self, startTime):
    """Tells the server to start generating the schema."""
    with requests.post(
      f'{self.serverAddress}/generate-schema/?bucketRootName={self.category}&sampleSize={self.sampleSize}&resolution={self.resolution}&force={self.force}',
      stream=True,
    ) as response:
      if response.status_code != 200:
        return None, response.status_code
      # Iterate over streamed lines
      for line in response.iter_lines():
        if line:
          try:
            data = json.loads(line.decode('utf-8'))
            # print('Stream update:', data)

            # Notify GUI for progress
            (
              totalDocuments,
              processedDocuments,
              totalSchemaTags,
              processedSchemaTags,
              schemaJsonString,
            ) = data['data']
            responseMessage = data['message']

            if self.progressBarCallback:
              self.progressBarCallback(
                totalDocuments,
                processedDocuments,
                totalSchemaTags,
                processedSchemaTags,
                schemaJsonString,
                responseMessage,
                startTime,
              )
          except json.JSONDecodeError:
            print('Invalid JSON chunk:', line)

      return 'Completed', schemaJsonString
