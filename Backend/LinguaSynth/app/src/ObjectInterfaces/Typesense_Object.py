import os
import json
from typing import Any
from Utils.ServerResponse import ServerResponseObject
from Managers.TypesenseManager import TypesenseManager

LLM_LIGHT_GENERATION_MODEL = 'gemma3:270m-it-bf16'  #'gemma3:1b-it-fp16'
LLM_HEAVY_GENERATION_MODEL = 'gemma3:4b'


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
  def IndexFileIntoCollection(self, document: dict[str, Any], collectionName: str):
    # if not self.collectionValid:
    # self.__ValidateCollectionExistence(collectionName)
    # insert the id into the summarized file
    # this is what is returned by the system when we search for a result.
    # jsonFile = json.loads(file)
    # # we have only been passed the fields
    # jsonFile['databaseID'] = fileId

    # file = json.dumps(jsonFile, separators=(',', ':'))
    # file = file.replace("'", '"')

    # Validate the file against the schema.
    # schema = self.GetSchema(collectionName)
    # validatedFile = map_to_schema(document=document, schema=schema)  # type: ignore
    self.client.serverResponseUtil.GenerateLogMessage(f'validatedFile {document}')
    return self.client.IndexDocuments(collectionName, document)

  def GetAllSchemas(self) -> dict[str, Any]:
    """
    Returns the schema that is currently loaded
    Return type is string so convert before modifying it.
    """
    # return only the fields, because everything else needs to remain the same.
    return self.client.GetLoadedSchemas()

  def GetSchema(self, schemaName: str) -> str:
    """
    Returns the schema object if it exists.
    Returns None if if does not.
    """
    for schema in self.client.GetLoadedSchemas():
      if schema['name'] == schemaName:  # type: ignore
        return json.dumps(schema)  # type: ignore
    return '' 

  def GetSchemaFields(self, schemaName: str) -> list[Any]:
    for schema in self.GetAllSchemas():
      if schema['name'] == schemaName:  # type: ignore
        return schema  # type: ignore
    return []

  def AskQuestion(
    self, searchSchema: str, query: str, minHits=2, maxHits=20, retries=2
  ) -> ServerResponseObject:
    result = self.client.NewQuery(searchSchema, query, minHits, maxHits)
    for i in range(0, retries):
      if not result.Success:
        result = self.client.NewQuery(searchSchema, query, minHits, maxHits)
      else:
        break

    if result.Success:
      return result

    # we tried x times and it still did not work.
    result.Data.update({'retires': 'max number of retires hit.'})
    return result
