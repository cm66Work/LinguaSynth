import csv
from dataclasses import asdict
import io
import json
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
    currentResponse.Message = (
      f'Generating Schemas for bucket: {targetBucketName}....'
    )
    yield self.serverResponse.GenerateServerResponse(currentResponse)

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

    currentResponse.TotalDocuments = self.minio.GetNumberOfObjectsInBucket(
      targetBucketName
    )
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    allKeyWords: list[str] = []
    currentResponse.Message = 'Collecting keywords from documents in bucket.'
    yield self.serverResponse.GenerateServerResponse(currentResponse)
    for document in self.minio.GetObjectsInBucket(targetBucketName):
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

    currentResponse.Message = (
      f'Done. Collected: {len(allKeyWords)} keywords. Generating schemas now.'
    )
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    pipelineResult = await pipeline.Run(allKeyWords, targetBucketName)

    if pipelineResult[1]:
      currentResponse.ProcessResponseObjects = pipelineResult[0]

    currentResponse.Success = True
    currentResponse.Finished = True
    currentResponse.Message = 'Finished'
    currentResponse.TotalTimeToComplete = (
      time.time() * 1000
    ) - generationStartTime
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    # Upload results in the event our browser crashes.
    currentJsonResponse = json.dumps(asdict(currentResponse), indent=1)
    currentJsonResponse = json.loads(currentJsonResponse)
    # We have to flatten the output.
    data = currentJsonResponse
    flatData = []

    for process in data.get('ProcessResponseObjects', []):
      for stat in process.get('Statistics', []):
        flatData.append(
          {
            # Top-level SchemaPipelineResponseObject
            'Success': data.get('Success'),
            'Message': data.get('Message'),
            'Finished': data.get('Finished'),
            'Total Time To Complete': data.get('TotalTimeToComplete'),
            'Total Documents': data.get('TotalDocuments'),
            # GeneratorResponseObject
            'Process Name': process.get('ProcessName'),
            # StatisticsObject
            'Target Schema Name': stat.get('targetSchemaName'),
            'Processing Time': stat.get('ProcessingTime'),
          }
        )

    memOutput = io.StringIO()
    writer = csv.DictWriter(memOutput, fieldnames=flatData[0].keys())
    writer.writeheader()
    writer.writerows(flatData)

    csvString = memOutput.getvalue()
    memOutput.close()
    self.minio.UploadDocumentToStorageServer(
      'n-schema-generation-results',
      csvString,
      'n-schema-generation.csv',
    )
