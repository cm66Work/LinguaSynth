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
