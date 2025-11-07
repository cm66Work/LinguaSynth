import json
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import (
  EmbeddingVectorSchemaGenerator,
  LLM_Object,
)
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils import JsonUtils


async def SchemaGeneration(
  minioObject: MinIO_Object,
  llmObject: LLM_Object,
  typesenseObject: Typesense_Object,
  serverResponse: ServerResponse,
):
  schemaGenerator: EmbeddingVectorSchemaGenerator = (
    EmbeddingVectorSchemaGenerator(llmObject, typesenseObject)
  )
  currentResponse = serverResponse.GenerateServerResponse(
    ServerResponseObject()
  )
  newSchema = await __ProcessAllDocumentsInBucket(minioObject, schemaGenerator)
  currentResponse.Data = {'schema': newSchema}
  currentResponse.Message = f'New schema generated: {newSchema["name"]}'  # type: ignore
  yield serverResponse.GenerateServerResponse(currentResponse)


async def __ProcessAllDocumentsInBucket(
  minioObject: MinIO_Object, schemaGenerator: EmbeddingVectorSchemaGenerator
):
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
  return newSchema


async def __GenerateTagsFromDocument(
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
    return await __GenerateTagsFromDocument(
      content, resolution, llmObject, existingTags
    )

  return existingTags
