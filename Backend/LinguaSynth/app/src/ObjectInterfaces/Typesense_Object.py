import os
from Utils.ServerResponse import ServerResponseObject
from Managers.TypesenseManager import TypesenseManager
from typesense.types.collection import CollectionSchema
from typing import Dict, Any

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

  def ImportSchema(
    self, schema: CollectionSchema, force: bool = False
  ) -> ServerResponseObject:
    return self.client.RecreateCollection(schema, force=force)

  # def CreateNewCollection(self):

  # TODO:: Convert this so we can process multiple index multiple files at a time.
  def IndexFileIntoCollection(self, document: str, collectionName: str):
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
    self.client.serverResponseUtil.GenerateLogMessage(
      f'validatedFile {document}'
    )
    return self.client.IndexDocuments(collectionName, document)

  def GetAllSchemas(self):
    """
    Returns the schema that is currently loaded
    Return type is string so convert before modifying it.
    """
    # return only the fields, because everything else needs to remain the same.
    return self.client.GetLoadedSchemas()

  def GetSchema(self, schemaName: str):
    """
    Returns the schema object if it exists.
    Returns None if if does not.
    """
    for schema in self.client.GetLoadedSchemas():
      if schema['name'] == schemaName:
        return schema
    return None

  def SchemaExists(self, schemaName) -> bool:
    if self.GetSchema(schemaName) is not None:
      return True
    return False

  def GetSchemaFields(self, schemaName: str):
    schema = self.GetSchema(schemaName)
    if schema is not None:
      return schema['fields']
    return None

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

  def Query(self, schemaName: str, query: str):
    return self.client.askQuery(schemaName, query)

  def DocumentSearch(self, collectionName: str):
    return self.client.DocumentSearch(collectionName, 50)

  def DeleteSchema(self, schemaName: str):
    return self.client.DeleteSchema(schemaName)

  def BuildUniversalTypesenseQuery(
    self,
    user_query: str,
    schema_name: str,
    limit: int = 10,
    sort_by: str | None = None,
  ) -> Dict[str, Any]:
    """
    Builds a Typesense query JSON object that searches across all available fields
    for a given schema. Uses '*' in the query_by parameter.

    Parameters
    ----------
    user_query : str
        The natural-language user query.
    schema_name : str
        The Typesense schema (collection) name.
    limit : int
        The number of search results to return.
    sort_by : str | None
        Optional sorting instruction (e.g., 'created_at:desc').

    Returns
    -------
    dict
        A ready-to-execute Typesense search query JSON object.
    """

    if not isinstance(user_query, str) or not user_query.strip():
      raise ValueError('user_query must be a non-empty string.')
    if not isinstance(schema_name, str) or not schema_name.strip():
      raise ValueError('schema_name must be a non-empty string.')

    query_payload = {
      # 'collection': schema_name,
      'q': user_query.strip(),
      'query_by': '*',  # Search across all textual fields
      'limit': limit,
      'num_typos': 2,
      'prefix': True,
      'drop_tokens_threshold': 1,
      'exhaustive_search': False,
      'highlight_full_fields': '*',
      'filter_by': '',
    }

    if sort_by:
      query_payload['sort_by'] = sort_by

    return query_payload
