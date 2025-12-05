import json
from APIs.Schema.EmbeddingVectorSchemaGenerator import (
  EmbeddingVectorSchemaGenerator,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils import JsonUtils


class GenerateSchema:
  def __init__(self) -> None:
    pass

  async def SplitSchema(
    self,
    minioObject: MinIO_Object,
    llmObject: LLM_Object,
    typesenseObject: Typesense_Object,
    serverResponse: ServerResponse,
    commonKeywordsFrequency: float = 0.45,
  ):
    schemaGenerator: EmbeddingVectorSchemaGenerator = (
      EmbeddingVectorSchemaGenerator(llmObject, typesenseObject)
    )
    currentResponse = serverResponse.GenerateServerResponse(
      ServerResponseObject()
    )
    newSchema = await self.__ProcessAllDocumentsInBucket(
      'testing-summarized',
      minioObject,
      schemaGenerator,
      commonKeywordsFrequency,
    )
    return
    currentResponse.Data = {'schema': newSchema}
    currentResponse.Message = f'New schema generated: {newSchema["name"]}'  # type: ignore
    yield serverResponse.GenerateServerResponse(currentResponse)

  async def __ProcessAllDocumentsInBucket(
    self,
    bucketName: str,  # schema bucket that needs to be reprocessed.
    minioObject: MinIO_Object,
    schemaGenerator: EmbeddingVectorSchemaGenerator,
    commonKeywordsFrequency: float = 0.45,
  ):
    allKeywords: list[str] = []
    for document in minioObject.GetObjectsInBucket(bucketName):
      if document.object_name is None:
        continue
      # Add the keywords from this document to the temp text file.
      content = (
        minioObject.GetContentOfBucketObject(
          bucketName, document.object_name
        ).Data['content']
      ).split(',')

      allKeywords.extend([keyword.strip() for keyword in content])
    print(allKeywords)

    allKeywordsAsString = ''
    print(allKeywordsAsString)
    return

    # We can just extract most frequent keywords from all the keywords.
    # This way we can select only the most common occurring keywords from all the documents.
    mostCommonKeywords = DocumentHelper.ExtractKeywords(
      allKeywordsAsString, commonKeywordsFrequency, 2
    )
    print(mostCommonKeywords)

    return

    bucketName = 'testing-summarized'
    schemaTemplate = {
      'name': 'default',
      'fields': [
        {'name': 'title', 'type': 'string'},
        {'name': 'author', 'type': 'string'},
      ],
    }
    newSchema = None
    for document in minioObject.GetObjectsInBucket(bucketName):
      if document.object_name is None:
        continue
      documentContent = minioObject.GetContentOfBucketObject(
        bucketName, document.object_name
      ).Data['content']
      if newSchema is None:
        newSchema = schemaTemplate
      newSchema = await schemaGenerator.ReprocessSchema(
        schemaTemplate,
        documentContent,
      )
    # We need to make sure these two fields are here since they are used to get the actual full document when the user searches for it.
    newSchema['fields'].append({'name': 'id', 'type': 'string'})  # type: ignore
    newSchema['fields'].append({'name': 'document_name', 'type': 'string'})  # type: ignore
    return newSchema

  async def __GenerateTagsFromDocument(
    self,
    content: str,
    resolution: int,
    llmObject: LLM_Object,
    existingTags: list[dict[str, str]] = [],
  ) -> list[dict[str, str]]:
    """
    Summarizes content into a JSON list of {tag, quote} objects, with recursion based on the resolution.
    """
    for paragraph in content.splitlines():
      if not paragraph.strip():
        continue
      response = await llmObject.Generate(
        f"""paragraph: {paragraph} 
              Summarize the content of this paragraph into a JSON list of tags. 
              Format per item: {{"tag": "string", "quote": "string"}}. 
              Summarize the "quote" to ~10 words. 
              Only return valid JSON."""
      )
      result = ' '.join(line.strip() for line in response.Response.splitlines())
      generated = json.loads(JsonUtils.TryConvertStringToJson(result))
      if not generated:
        continue

      def __flatten_tags(nested):
        """
        Flattens a nested set of tags and returns a list of tags with a depth of 1
        [[[[]]]] -> []
        """
        flat = []
        for item in nested:
          if isinstance(item, list):
            flat.extend(__flatten_tags(item))  # recursion.
          elif isinstance(item, dict):
            flat.append(item)
        return flat

      existingTags.extend(__flatten_tags(generated['matches']))
    resolution -= 1
    if resolution > 0:
      return await self.__GenerateTagsFromDocument(
        content, resolution, llmObject, existingTags
      )

    return existingTags
