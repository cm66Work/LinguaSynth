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
            print(f'{data} \n\n')
            # print('Stream update:', data)
            totalDocuments = int(data['Data'].get('total_documents_to_process', 1))
            processedDocuments = int(data['Data'].get('processed_document_count', 0))
            totalSchemaTags = int(data['Data'].get('total_schema_tags', 1))
            processedSchemaTags = int(data['Data'].get('processed_schema_tags', 0))
            schemaJsonString = data['Data'].get('schema_json_string', '')

            responseMessage = data['Message']

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
