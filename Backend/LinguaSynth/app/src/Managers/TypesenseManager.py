from Utils.ServerResponse import ServerResponse, ServerResponseObject
from typesense.client import Client


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

    self.serverResponseUtil = ServerResponse('Typesense', 'typesense_log')

  def RecreateCollection(self, schema, schemaName: str) -> ServerResponseObject:
    """
    Deletes and recreates a new collection with the provides schema.
    Args:
        schema: The schema used in the collection.
    """
    try:
      self.client.collections[schemaName].delete()
    except Exception as e:
      self.serverResponseUtil.GenerateLogMessage(
        f'Exception::TypesenseManager.CreateCollection:: {e}. \nSkipping deletion of document.'
      )
    try:
      result = self.client.collections.create(schema)
      # make sure it's JSON serializable
      safe_result = dict(result) if not isinstance(result, dict) else result

      return self.serverResponseUtil.GenerateServerResponse(
        success=True, message='', extraData={'result': safe_result}
      )
    except Exception as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False,
        message=f'Exception::TypesenseManager.CreateCollection:: {e}',
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

  def IndexDocuments(self, collection: str, documents: list[dict]):
    """
    Imports document content into Typesense
    Args:
        collection (str): Collection used to store the file.
        documents (JSONLines): JSONLines list of documents to upload.
          Format = [{id, schema files...},]
    """
    result = self.client.collections[collection].documents.import_(
      documents,  # type: ignore
      {'action': 'upsert'},
    )

    # Import method does not fail if a document fails to upload.
    # So we need to sort our the failed documents from the success documents.
    # Reasons for the failed upload are provided in the return object for each document.
    errorList = []
    for r in result:
      if not r['success']:
        errorList.append(r)
    if len(errorList) > 0:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False,
        message=f'ERROR::TypesenseManager.IndexDocuments:: {len(errorList)} number of documents failed to import, see logs for more details',
        extraData={'errors': errorList},
      )
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
