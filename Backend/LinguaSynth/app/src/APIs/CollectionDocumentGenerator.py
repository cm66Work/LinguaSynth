import asyncio
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import csv
from dataclasses import asdict
import io
import json
import time
from typing import AsyncGenerator, cast, Any
from APIs.ProcessingPipeline import CollectionDocumentGenerationPipeline
from APIs.ProcessingPipeline.CollectionDocumentGenerationPipeline import (
  CollectionDocumentGenerationPipeline,
  CollectionDocumentGenerationPipelineResponseObject,
)
from APIs.ProcessingPipeline.CollectionDocumentGenerators.ICollectionDocumentGenerator import (
  CollectionDocumentGenerationResponseObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import (
  LLM_Object,
)
from Utils.LogUtils import ErrorTypes
from typesense.types.document import DocumentSchema
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.ServerResponse import (
  ServerResponseV2,
  ServerResponseObject,
)
from typesense.types.collection import CollectionSchema


class CollectionDocumentGenerator:
  def __init__(
    self,
    minio: MinIO_Object,
    llm: LLM_Object,
    typesense: Typesense_Object,
    serverResponse: ServerResponseV2,
  ) -> None:
    self.minio = minio
    self.llm = llm
    self.typesense = typesense
    self.serverResponse = serverResponse

  async def RunGenerators(
    self, targetDataBucket: str, schemaName: str
  ) -> AsyncGenerator[ServerResponseObject, Any]:
    currentResponse = CollectionDocumentGenerationPipelineResponseObject()
    currentResponse.Message = 'Ingesting....'
    currentResponse.CollectionName = schemaName
    pipeline: CollectionDocumentGenerationPipeline = (
      CollectionDocumentGenerationPipeline(
        self.minio, self.llm, self.serverResponse, targetDataBucket, schemaName
      )
    )
    self.tempPipeline = pipeline

    indexingStartTime: float = time.time() * 1000
    if not await self.minio.BucketExists(targetDataBucket):
      currentResponse.Message = (
        f'No bucket with name: {targetDataBucket} found.'
      )
      currentResponse.Finished = True
      yield self.serverResponse.GenerateServerResponse(
        currentResponse, className=__name__, errorType=ErrorTypes.Error
      )
      return
    currentResponse.NumberOfDocumentsToProcess = (
      self.minio.GetNumberOfObjectsInBucket(targetDataBucket)
    )
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    try:
      schema: CollectionSchema = cast(
        CollectionSchema, self.typesense.GetSchema(schemaName)
      )
      if schema is None:
        raise Exception('Schema is None')
    except Exception as e:
      currentResponse.Message = f'Failed to cast to CollectionSchema: {e}'
      yield self.serverResponse.GenerateServerResponse(
        currentResponse, __name__, ErrorTypes.Error
      )
      return

    documentSchema = self.__ConvertToDocumentSchema(schema)

    totalDocuments: int = self.minio.GetNumberOfObjectsInBucket(
      targetDataBucket
    )
    processedDocuments: int = 0
    for document in self.minio.GetObjectsInBucket(targetDataBucket):
      lastDocumentProcessingTime = time.time()
      currentResponse.DocumentsProcessed += 1
      if document.object_name is None:
        continue
      content: str = self.minio.GetContentOfBucketObject(
        targetDataBucket, document.object_name
      ).Data['content']
      result = await pipeline.Run(
        content,
        document.object_name,
        documentSchema,
        schema['name'],
      )
      if result[1]:
        currentResponse.IngestedResponseObjects = result[0]
      processedDocuments += 1
      timeTaken = time.time() - lastDocumentProcessingTime
      print(
        f'Processed: {processedDocuments}/{totalDocuments} documents. ETA: {timeTaken * (totalDocuments - processedDocuments)}'
      )

    currentResponse.Success = True
    currentResponse.Finished = True
    currentResponse.Message = 'Finished'
    currentResponse.TotalTimeToComplete = (
      time.time() * 1000
    ) - indexingStartTime
    currentResponse.AverageTimeToProcessEachDocument = (
      currentResponse.TotalTimeToComplete / currentResponse.DocumentsProcessed
    )
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    # Upload results in the event our browser crashes.
    currentJsonResponse = json.dumps(asdict(currentResponse), indent=1)
    currentJsonResponse = json.loads(currentJsonResponse)
    # We have to flatten the output.
    data = currentJsonResponse
    flatData = []

    for process in data.get('IngestedResponseObjects', []):
      for stat in process.get('Statistics', []):
        flatData.append(
          {
            # Top-level SchemaPipelineResponseObject
            'Success': data.get('Success'),
            'Message': data.get('Message'),
            'Finished': data.get('Finished'),
            'Total Time To Complete': data.get('TotalTimeToComplete'),
            'Number Of Documents To Process': data.get(
              'NumberOfDocumentsToProcess'
            ),
            # Ingested Response Objects
            'Process Name': process.get('ProcessName'),
            # Statistics Object
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
      'n-document-generation-results',
      csvString,
      'n-document-generation.csv',
    )

  def __ConvertToDocumentSchema(
    self, schema: CollectionSchema
  ) -> DocumentSchema:
    documents: dict[str, str] = {}
    for field in schema['fields']:
      documents[field['name']] = field['type']  # type: ignore

    documentsConstants: dict[str, str] = {'id': 'string'}
    documents.update(documentsConstants)

    return cast(DocumentSchema, documents)
