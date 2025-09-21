import os
import json
from Utils.ServerResponse import ServerResponseObject
from Managers.TypesenseManager import TypesenseManager


class Typesense_Object:
  def __init__(self):
    self.client = TypesenseManager(
      host=os.getenv('TYPESENSE_HOST', 'typesense'),
      port=os.getenv('TYPESENSE_PORT', '8108'),
      protocol=os.getenv('TYPESENSE_PROTOCOL', 'http'),
      apiKey=os.getenv('TYPESENSE_API_KEY', 'xyz'),
      searchApiKey=os.getenv('TYPESENSE_SEARCH_API_KEY', 'xyz'),
    )
    self.collectionValid = False

  def ImportSchema(self, schema, force: bool = False) -> ServerResponseObject:
    # convert to dic to make things easier.
    # processedSchema = json.loads(schema)
    # processedSchema = self.__MutateSchema(schema)
    return self.client.RecreateCollection(schema, force)

  # def CreateNewCollection(self):

  # TODO:: Convert this so we can process multiple index multiple files at a time.
  def IndexFileIntoCollection(self, file: str, fileId: int, collectionName: str):
    # if not self.collectionValid:
    # self.__ValidateCollectionExistence(collectionName)
    # insert the id into the summarized file
    # this is what is returned by the system when we search for a result.
    jsonFile = json.loads(file)
    # we have only been passed the fields
    jsonFile['databaseID'] = fileId

    file = json.dumps(jsonFile, separators=(',', ':'))
    file = file.replace("'", '"')

    return self.client.IndexDocuments(collectionName, str([file]))

  def UserSearchQuery(self, collectionName: str = '', userQuery: str = ''):
    if not self.collectionValid:
      pass
      # self.__ValidateCollectionExistence(collectionName)
    # TODO:: process user question and return results.

  # def __ValidateCollectionExistence(self, collectionName: str):
  #   if not self.client.CollectionExists(collectionName):
  #     self.CreateNewCollection()

  def GetSchemaContent(self) -> str:
    """
    Returns the schema that is currently loaded
    Return type is string so convert before modifying it.
    """
    schema = self.client.GetLoadedSchemas()

    self.client.serverResponseUtil.GenerateLogMessage(f'here -->> {schema}')
    # return only the fields, because everything else needs to remain the same.
    result = json.loads(str(schema))
    self.client.serverResponseUtil.GenerateLogMessage(f'here -->> {result}')
    return json.dumps(result)

  def GetSchemaFields(self) -> str:
    result = json.loads(self.GetSchemaContent())
    return json.dumps(result['fields'])
