import os
import json
from typing import Any
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

  def ImportSchema(self, schema: str, force: bool = False) -> ServerResponseObject:
    # convert to dic to make things easier.
    # processedSchema = json.loads(schema)
    # processedSchema = self.__MutateSchema(schema)
    # ensure that we are processing a python dict not a json like string
    # <class 'str'>
    jsonSchema: dict[str, Any] = json.loads(schema)
    return self.client.RecreateCollection(jsonSchema, force=force)

  # def CreateNewCollection(self):

  # TODO:: Convert this so we can process multiple index multiple files at a time.
  def IndexFileIntoCollection(self, files: list[str], collectionName: str):
    # if not self.collectionValid:
    # self.__ValidateCollectionExistence(collectionName)
    # insert the id into the summarized file
    # this is what is returned by the system when we search for a result.
    # jsonFile = json.loads(file)
    # # we have only been passed the fields
    # jsonFile['databaseID'] = fileId

    # file = json.dumps(jsonFile, separators=(',', ':'))
    # file = file.replace("'", '"')
    return self.client.IndexDocuments(collectionName, files[0])

  def UserSearchQuery(self, collectionName: str = '', userQuery: str = ''):
    if not self.collectionValid:
      pass
      # self.__ValidateCollectionExistence(collectionName)
    # TODO:: process user question and return results.

  # def __ValidateCollectionExistence(self, collectionName: str):
  #   if not self.client.CollectionExists(collectionName):
  #     self.CreateNewCollection()

  def GetAllSchemas(self) -> dict[str, Any]:
    """
    Returns the schema that is currently loaded
    Return type is string so convert before modifying it.
    """
    # return only the fields, because everything else needs to remain the same.
    return self.client.GetLoadedSchemas()

  def GetSchema(self, schemaName: str) -> dict[str, Any] | None:
    """
    Returns the schema object if it exists.
    Returns None if if does not.
    """
    for schema in self.client.GetLoadedSchemas():
      if schema['name'] == schemaName:  # type: ignore
        return schema  # type: ignore
    return None

  def GetSchemaFields(self, schemaName: str) -> list[Any]:
    for schema in self.GetAllSchemas():
      if schema['name'] == schemaName:  # type: ignore
        return schema  # type: ignore
    return []
