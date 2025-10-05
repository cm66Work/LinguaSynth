import json
from typing import Any
from Utils.LogUtils import ErrorTypes
from Utils.ServerResponse import ServerResponse, ServerResponseObject
import requests
from typesense.client import Client
from typesense.types.collection import CollectionCreateSchema

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

  def CanOverrideSchema(self, schema: dict[str, Any], force=False) -> bool:
    """
    Replaces the existing schema with a new one.
    Args:
        schema (dict): New schema.
        force (bool): If the, will not stop override of schema if one already exists.
    """
    if isinstance(schema, str):
      schema = json.loads(schema)
    if len(schema['fields']) > 0 and not force:
      self.serverResponseUtil.GenerateLogMessage(
        'ERROR::TypesenseManager.SetSchema:: Can not override existing schema with out force'
      )
      return False
    elif len(schema['fields']) > 0 and force:
      self.serverResponseUtil.GenerateLogMessage(
        'WARNING::TypesenseManager.SetSchema:: Forcing override of existing schema.'
      )
    self.serverResponseUtil.GenerateLogMessage(
      f'Setting new schema. List:{self.client.collections.retrieve()}'
    )
    return True

  def CollectionExists(self, collectionName: str) -> bool:
    for collection in self.GetLoadedSchemas():
      # jsonCollection: dict[str, Any] = json.loads(str(collection).replace("'", '"'))
      if collection['name'] == collectionName:  # type: ignore
        return True
    return False

  def RecreateCollection(
    self, newSchema: dict[str, Any], force=False
  ) -> ServerResponseObject:
    """
    Deletes and recreates a new collection with the provides schema.
    Args:
        schema: The schema used in the collection.
    """
    if not bool(newSchema.get('fields')):
      return self.serverResponseUtil.GenerateServerResponse(
        success=False,
        message='New schema is empty',
        errorType=ErrorTypes.Warning,
        className=self.__class__.__name__,
      )
    if not self.CanOverrideSchema(schema=newSchema, force=force):
      return self.serverResponseUtil.GenerateServerResponse(
        success=False,
        message='Cannot override existing schema',
        errorType=ErrorTypes.Warning,
        className=self.__class__.__name__,
      )

    if force and self.CollectionExists(newSchema['name']):
      self.client.collections[newSchema['name']].delete()

    try:
      # create the schema
      # ignore the pylance typing error it is fine.
      result = self.client.collections.create(newSchema)  # type: ignore
      # make sure it's JSON serializable
      safe_result = dict(result) if not isinstance(result, dict) else result

      return self.serverResponseUtil.GenerateServerResponse(
        success=True, extraData={'result': safe_result}
      )
    except Exception as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False,
        message=f'{e}',
        errorType=ErrorTypes.Exception,
        className=self.__class__.__name__,
      )

  def DeleteCollection(self, name: str):
    """
    Deletes the collection if it exists.
    Args:
        name (str): Collection name to be deleted.
    """
    try:
      result = self.client.collections[name].delete()
      return self.serverResponseUtil.GenerateServerResponse(
        success=True, message=f'Deleted collection {name}', extraData={'result': result}
      )
    except Exception as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False, message=f'EXCEPTION::Typesense.DeleteCollection:: {e}'
      )

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
        success=False, message=f'{e}', errorType=ErrorTypes.Warning, generateLog=False
      )

  # region Tools
  def GetLoadedSchemas(self) -> dict[str, Any]:
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
