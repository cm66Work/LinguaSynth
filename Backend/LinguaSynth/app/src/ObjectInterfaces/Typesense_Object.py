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
    schema = self.GetSchema(collectionName)
    validatedFile = map_to_schema(document=document, schema=schema)  # type: ignore
    self.client.serverResponseUtil.GenerateLogMessage(f'validatedFile {validatedFile}')
    return self.client.IndexDocuments(collectionName, validatedFile)

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

  # def AskQuestion(self, searchSchema: str, question: str) -> ServerResponseObject:
  #   return self.client.nlSearch(
  #     collection=searchSchema,
  #     question=question,
  #     minHits=0,
  #     queryBy='dessert_name',
  #     model=LLM_HEAVY_GENERATION_MODEL,
  #   )

  def AskQuestion(self, searchSchema: str, query: str) -> ServerResponseObject:
    return self.client.NewQuery(searchSchema, query)


# region Utils
def default_value(expected_type: str):
  """Return a safe default value for a Typesense type."""
  if expected_type == 'string':
    return ''
  elif expected_type == 'int32':
    return 0
  elif expected_type == 'int64':
    return 0
  elif expected_type == 'float':
    return 0.0
  elif expected_type == 'bool':
    return False
  elif expected_type.endswith('[]'):
    return []
  return None


def coerce_value(value: Any, expected_type: str):
  """Coerce value into Typesense schema type safely."""
  try:
    if value is None or value == '':
      return default_value(expected_type)

    if expected_type == 'string':
      return str(value)
    elif expected_type == 'int32':
      return int(float(value))  # allows "42.0" → 42
    elif expected_type == 'float':
      return float(value)
    elif expected_type == 'bool':
      if isinstance(value, bool):
        return value
      if str(value).lower() in ['true', '1', 'yes']:
        return True
      if str(value).lower() in ['false', '0', 'no']:
        return False
      return default_value('bool')
    elif expected_type.endswith('[]'):
      inner_type = expected_type[:-2]
      if not isinstance(value, list):
        value = [value]  # wrap non-list into a list
      return [coerce_value(v, inner_type) for v in value]
  except Exception:
    return default_value(expected_type)

  return default_value(expected_type)


def map_to_schema(document: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
  """Always return a document that matches schema, filling missing or bad values with defaults."""
  mapped_doc = {}
  for field in schema['fields']:
    name = field['name']
    expected_type = field['type']
    raw_value = document.get(name, None)
    mapped_doc[name] = coerce_value(raw_value, expected_type)
  return mapped_doc
