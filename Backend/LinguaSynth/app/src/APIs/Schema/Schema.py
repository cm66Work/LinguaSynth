import time
from typing import Any, AsyncGenerator, cast
from APIs.ProcessingPipeline.SchemaGeneration.ISchemaGenerator import (
  GeneratorResponseObject,
)
from APIs.Schema.EmbeddingVectorSchemaGenerator import (
  EmbeddingVectorSchemaGenerator,
)
from APIs.ProcessingPipeline.SchemaPipeline import (
  SchemaPipeline,
  SchemaPipelineResponseObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from Utils.ServerResponse import ServerResponseV2, ServerResponseObject
from Utils.LogUtils import ErrorTypes
from Utils import JsonUtils


class Schema:
  def __init__(
    self, minio: MinIO_Object, serverResponse: ServerResponseV2, llm: LLM_Object
  ) -> None:
    self.minio = minio
    self.serverResponse = serverResponse
    self.llm = llm

  async def Generate(
    self, targetBucketName: str
  ) -> AsyncGenerator[ServerResponseObject, Any]:
    currentResponse = SchemaPipelineResponseObject()
    currentResponse.Message = 'Processing....'
    pipeline: SchemaPipeline = SchemaPipeline(
      self.minio, self.llm, self.serverResponse
    )
    generationStartTime: float = time.time() * 1000
    # start processing all documents in this bucket using our different processing pipelines.
    if not await self.minio.BucketExists(targetBucketName):
      currentResponse.Message = (
        f'No bucket with name: {targetBucketName} found.'
      )
      currentResponse.Finished = True
      yield self.serverResponse.GenerateServerResponse(
        currentResponse,
        className=__name__,
        errorType=ErrorTypes.Error,
      )
      return

    currentResponse.NumberOfDocumentsProcessed = (
      self.minio.GetNumberOfObjectsInBucket(targetBucketName)
    )
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    allKeyWords: list[str] = []
    for document in self.minio.GetObjectsInBucket(targetBucketName):
      currentResponse.TotalDocumentsProcessed += 1
      if document.object_name is None:
        continue
      content = cast(
        str,
        self.minio.GetContentOfBucketObject(
          targetBucketName, document.object_name
        ).Data['content'],
      )
      content = [word.strip() for word in content.split(',')]
      allKeyWords.extend(content)

    pipelineResult = await pipeline.Run(allKeyWords, targetBucketName)

    if pipelineResult[1]:
      currentResponse.ProcessResponseObjects = pipelineResult[0]

    currentResponse.Success = True
    currentResponse.Finished = True
    currentResponse.Message = 'Finished'
    currentResponse.TotalTimeToComplete = (
      time.time() * 1000
    ) - generationStartTime
    currentResponse.AverageTimeToProcessEachDocument = (
      currentResponse.TotalTimeToComplete
      / currentResponse.NumberOfDocumentsProcessed
    )
    yield self.serverResponse.GenerateServerResponse(currentResponse)
    return

  # -------------

  async def SplitSchema(
    self, bucketName: str
  ) -> AsyncGenerator[ServerResponseObject, Any]:
    currentResponse = GeneratorResponseObject()
    currentResponse.Message = 'Processing.....'
    currentResponse.TotalDocumentsProcessed = (
      self.minio.GetNumberOfObjectsInBucket(bucketName)
    )
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    # Collect all keywords from the given bucket into two different lists.
    content: tuple[list[str], list[str]] = [], []
    for document in self.minio.GetObjectsInBucket(bucketName):
      currentResponse.CurrentDocumentsProcessed += 1
      if document.object_name is None:
        continue
      text = self.minio.GetContentOfBucketObject(
        bucketName, document.object_name
      ).Data['content']
      if currentResponse.CurrentDocumentsProcessed % 2 == 0:
        # we are eve
        content[0].append(text)
      else:
        # we are odd
        content[1].append(text)
      print('\n\n', content)

    # pipeline: SchemaGeneratorPipeline = SchemaGeneratorPipeline(
    #   self.minio, self.serverResponse
    # )

    # Get a list of all "raw"

    yield self.serverResponse.GenerateServerResponse(currentResponse)
    return
    # schemaGenerator: EmbeddingVectorSchemaGenerator = (
    #   EmbeddingVectorSchemaGenerator(llmObject, typesenseObject)
    # )
    # currentResponse = serverResponse.GenerateServerResponse(
    #   GeneratorResponseObject()
    # )
    # newSchema = await self.__ProcessAllDocumentsInBucket(
    #   'testing-summarized',
    #   minioObject,
    #   schemaGenerator,
    #   commonKeywordsFrequency,
    # )
    # return
    # currentResponse.Data = {'schema': newSchema}
    # currentResponse.Message = f'New schema generated: {newSchema["name"]}'  # type: ignore
    # yield serverResponse.GenerateServerResponse(currentResponse)

  async def GenerateNewSchemaFromContent(self, content: str):
    pass

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
