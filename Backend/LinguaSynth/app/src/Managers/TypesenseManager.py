import json
from typing import Any
from Utils.LogUtils import ErrorTypes
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from typesense.client import Client
from typesense.types.collection import CollectionCreateSchema


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
      if collection['name'] == collectionName:
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

  def IndexDocuments(self, collection: str, docs: str):
    """
    Imports document content into Typesense
    Args:
        collection (str): Collection used to store the file.
        documents (JSONLines): JSONLines list of documents to upload.
          Format = [{id, schema files...},]
    """
    result = self.client.collections[collection].documents.import_(
      documents=docs, import_parameters={'action': 'upsert'}
    )

    # Import method does not fail if a document fails to upload.
    # So we need to sort our the failed documents from the success documents.
    # Reasons for the failed upload are provided in the return object for each document.
    # TODO:: fix response error handling, result could have a return of a list or string
    # errorList = []
    # for r in result:
    #   if not r['success']:
    #     errorList.append(r)
    # if len(errorList) > 0:
    #   return self.serverResponseUtil.GenerateServerResponse(
    #     success=False,
    #     message=f'ERROR::TypesenseManager.IndexDocuments:: {len(errorList)} number of documents failed to import, see logs for more details',
    #     extraData={'errors': errorList},
    #   )
    return self.serverResponseUtil.GenerateServerResponse(
      success=True,
      message=f'{len(result)} documents uploaded successfully.',
      extraData={'result': result},
    )

  def NewQuery(
    self, collection: str, question: str, queryBy='content,name', minHits=2, maxHits=20
  ):
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
    search_params = {
      'q': question,
      'query_by': queryBy,
    }
    results = self.client.collections[collection].documents.search(search_params)  # type: ignore
    hits = results.get('hits', [])
    n = len(hits)

    responseMessage = ''
    confidence = 0
    documentNames = [h['document']['name'] for h in hits]
    if n < minHits:
      responseMessage = 'Not sure of the answer.'
      confidence = -1
    elif n > maxHits:
      responseMessage = 'Question is not clear enough.'
      confidence = 0
    else:
      responseMessage = f'Found {n} documents.'
      confidence = 1

    return self.serverResponseUtil.GenerateServerResponse(
      success=True,
      message=f'Found {len(documentNames)} related to user query.',
      extraData={
        'responseMessage': responseMessage,
        'confidence': confidence,
        'documents': documentNames,
      },
    )

  # region Tools
  def GetLoadedSchemas(self):
    return self.client.collections.retrieve()

  # endregion
