import json
from typing import Any, cast
from Utils.LogUtils import ErrorTypes
from Utils.ServerResponse import ServerResponse, ServerResponseObject
import requests
from typesense.client import Client
from typesense.types.collection import CollectionCreateSchema, CollectionSchema
from typesense.types.document import DocumentSchema

OLLAMA_HOST = 'http://ollama:11434'


class TypesenseManager:
  def __init__(
    self,
    host: str,
    port: str,
    protocol: str,
    apiKey: str,
    searchApiKey: str,
  ):
    self.client = Client(
      {
        'api_key': apiKey,  # ignore to fix unhappy type checker...Pylance
        'nodes': [{'host': host, 'port': port, 'protocol': protocol}],  # type: ignore
        'connection_timeout_seconds': 5,
      }
    )
    self.typesenseURL = f'http://{host}:{port}'
    self.apiKey = apiKey

    # have to create the model inside typesense before we can use it.
    self.nlModelId = 'default-search'
    payload = {
      'id': f'{self.nlModelId}',
      'model_name': 'ollama/gemma3:270m-it-bf16',
      'api_url': 'http://ollama:11434/api/generate',
      'max_bytes': 16000,
      'temperature': 0.0,
      'system_prompt': '',
    }
    self.model = requests.post(url=self.typesenseURL, json=payload)

    # typesense maps this to a
    self.schema: CollectionCreateSchema = {'name': 'default', 'fields': []}
    self.serverResponseUtil = ServerResponse('Typesense', 'typesense_log')

  def CanOverrideSchema(self, schema: CollectionSchema, force=False) -> bool:
    """
    Replaces the existing schema with a new one.
    Args:
        schema (dict): New schema.
        force (bool): If the, will not stop override of schema if one already exists.
    """
    if len(schema['fields']) > 0 and not force:
      self.serverResponseUtil.GenerateLogMessage(
        'ERROR::TypesenseManager.SetSchema:: Can not override existing schema with out force'
      )
      return False
    elif len(schema['fields']) > 0 and force:
      self.serverResponseUtil.GenerateLogMessage(
        'WARNING::TypesenseManager.SetSchema:: Forcing override of existing schema.'
      )
    return True

  def SchemaExists(self, collectionName: str) -> bool:
    for schema in self.GetLoadedSchemas():
      if schema['name'] == collectionName:  # type: ignore
        return True
    return False

  def RecreateCollection(
    self, schemaName: str, newSchema: str, force=False
  ) -> ServerResponseObject:
    """
    Deletes and recreates a new collection with the provides schema.
    Args:
        schema: The schema used in the collection.
    """
    # try to cast the given schema to the Typesense schema.
    # This creates a nice layer of separation between the interface and the manager.
    try:
      validationResponse = self.__SchemaCreationValidation(schemaName, force)
      # run validation checks
      if validationResponse.Finished:
        # Validation failed.
        return validationResponse

      if self.SchemaExists(schemaName):
        try:
          self.client.collections[schemaName].delete()
        except Exception as e:
          return self.serverResponseUtil.GenerateServerResponse(
            success=False,
            message=f'Failed to delete schema: {e}',
            errorType=ErrorTypes.Exception,
            className=self.__class__.__name__,
            finished=True,
          )

      schema = json.loads(newSchema)
      schema = cast(CollectionSchema, schema)
      schema['name'] = schemaName
      schema['enable_nested_fields'] = True

      try:
        """ For objects in the schema we need to flatten them.
            They can be accessed using . notation.
            For example, address.buildingNumber, or person.name
        """
        schemaFields: list = []
        for field in schema['fields']:
          objectFields: list[dict] = field.get('fields', [])
          if objectFields == []:
            schemaFields.append(field)
          else:
            # we have a nested object.
            for objectField in objectFields:
              objectField['name'] = field['name'] + '.' + objectField['name']  # type: ignore
              schemaFields.append(objectField)
        schema['fields'] = schemaFields

        # create the schema
        result = self.client.collections.create(schema)
        return self.serverResponseUtil.GenerateServerResponse(
          success=True, extraData={'result': result}, finished=True
        )
      except Exception as e:
        return self.serverResponseUtil.GenerateServerResponse(
          success=False,
          message=f'Failed to create schema: {e}',
          errorType=ErrorTypes.Exception,
          className=self.__class__.__name__,
          finished=True,
        )
    except Exception as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False,
        message=f'{e} Failed to cast schema to Typesense schema type',
        errorType=ErrorTypes.Error,
        className=self.__class__.__name__,
        finished=True,
      )

  def __SchemaCreationValidation(
    self,
    schemaName: str,
    force: bool = False,
  ):
    validationResponse = self.serverResponseUtil.GenerateServerResponse(
      success=False,
      message='',
      extraData={},
      className=__class__.__name__,
      finished=False,
    )
    if len(schemaName) <= 0:
      validationResponse.Message = (
        'Entered schema name is empty. Canceling upload of new schema.'
      )
      validationResponse.Success = False
      validationResponse.Finished = True
      return validationResponse

    if self.SchemaExists(schemaName) and not force:
      validationResponse.Success = False
      validationResponse.Finished = True
      validationResponse.Message = 'Schema already exists. Schema overriding is currently protected. Set force to True to disable override protection.'
      return validationResponse
    elif self.SchemaExists(schemaName) and force:
      validationResponse.Success = True
      validationResponse.Finished = False
      validationResponse.Message = 'Forcing override of existing schema.'
      return validationResponse

    return validationResponse

  def IndexDocuments(self, collectionName: str, docs: dict[str, Any]):
    """
    Imports document content into Typesense
    Args:
        collection (str): Collection used to store the file.
        documents (JSONLines): JSONLines list of documents to upload.
          Format = [{id, schema files...},]
    """

    try:
      # result = self.client.collections[collection].documents.import_(
      #   documents=docs, import_parameters={'action': 'upsert'}
      # )
      # document = json.loads(docs)
      result = self.client.collections[collectionName].documents.upsert(docs)
      self.serverResponseUtil.GenerateLogMessage(
        f'loaded: {self.client.collections[collectionName].retrieve()}'
      )
      return self.serverResponseUtil.GenerateServerResponse(
        success=True,
        message=f'{result} documents uploaded successfully. {self.client.collections[collectionName].documents.export()}',
        extraData={'result': result},
      )
    except Exception as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False,
        message=f'documents uploaded Failed to index. {e}',
        errorType=ErrorTypes.Error,
      )

  def NewQuery(self, collectionName: str, query, minHits=2, maxHits=20):
    """
    Queries typesense and applies rule response filters.
    Args:
        collection (str): Collection to query.
        question (str): User query.
        queryBy (): One or more field names that should be queried against (like adding filters to a search).
        minHits (int): Number of hits required for the system to feel confident in the answer.
        maxHits (int): Number of hits to trigger a "Question is not clear enough" response.
    Returns:
        Part of the return is extra data containing the following keys:
          responseMessage (key:string): default answers to too few or too many documents being returned.
          confidence (key: int): range from -1 to 1 based on how confident the system is about the response.
          documents (key list[str]): Names of documents found.
    """
    try:
      query = json.loads(query)
      results = self.client.collections[collectionName].documents.search(query)
      self.serverResponseUtil.GenerateLogMessage(f'result:{results}')
      hits = results.get('hits', [])
      n = len(hits)

      responseMessage = ''
      confidence = 0
      # documentNames = [h['document']['name'] for h in hits]
      if n < minHits or n == 0:
        responseMessage = """
        You are not sure of the answer and cant answer.
        refuse to answer the question as you do not know the answer.
        You do not have the information loaded in your database.
        """
        confidence = -1
      elif n > maxHits:
        responseMessage = """
        The users questions not clear enough.
        Refuse to answer the question and instead ask if the user could be a little more specific.
        """
        confidence = 0
      else:
        responseMessage = f'Found {n} documents.'
        confidence = 1

      return self.serverResponseUtil.GenerateServerResponse(
        success=True,
        message=f'Found {len(hits)} related to user query.',
        extraData={
          'responseMessage': responseMessage,
          'confidence': confidence,
          'documents': hits,
        },
      )
    except Exception as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False,
        message=f'{e}',
        errorType=ErrorTypes.Warning,
        generateLog=False,
      )

  # region Tools
  def GetLoadedSchemas(self):
    # ignoring the pylance error, the type is correct.
    return self.client.collections.retrieve()  # type: ignore

  # endregion

  # region Asking questions
  def askQuery(self, collectionName: str, query) -> ServerResponseObject:
    try:
      query = json.loads(query)
      result = self.client.collections[collectionName].documents.search(query)
      return self.serverResponseUtil.GenerateServerResponse(
        success=True, message='testing', extraData={'result': result}
      )
    except Exception as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False,
        message=f'Failed to answer user question {e}',
        extraData={},
        errorType=ErrorTypes.Exception,
      )

  # endregion

  def GetAllModels(self):
    url = f'{self.typesenseURL}/nl_search_models'

    headers = {
      'X-TYPESENSE-API-KEY': self.apiKey,
      'Content-Type': 'application/json',
    }
    resp = requests.get(url, headers=headers, timeout=60)
    return self.serverResponseUtil.GenerateServerResponse(
      success=resp.ok, message=str(resp.content)
    )

  def LoadModel(self):
    self.nlModelId = 'default-search'
    payload = {
      'id': f'{self.nlModelId}',
      'model_name': 'ollama/gemma3:270m-it-bf16',
      'api_url': 'http://ollama:11434/api/generate',
      'max_bytes': 16000,
      'temperature': 0.0,
      'system_prompt': '',
    }
    headers = {
      'X-TYPESENSE-API-KEY': self.apiKey,
      'Content-Type': 'application/json',
    }
    resp = requests.post(
      url=f'{self.typesenseURL}/nl_search_models', headers=headers, json=payload
    )
    return self.serverResponseUtil.GenerateServerResponse(
      success=resp.ok, message=str(resp.content)
    )
