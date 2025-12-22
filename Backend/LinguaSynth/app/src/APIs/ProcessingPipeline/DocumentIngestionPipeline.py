import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Any, cast
from APIs.ProcessingPipeline.DocumentIngestors.IDocumentIngestor import (
  IDocumentIngestor,
  DocumentIngestionResponseObject,
  StatisticObject,
)
from APIs.ProcessingPipeline.DocumentIngestors.SimpleDocumentIngestion import (
  SimpleDocumentIngestion,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.ServerResponse import (
  ServerResponseV2,
  ServerResponseObject,
)


@dataclass
class DocumentIngestionPipelineResponseObject(ServerResponseObject):
  TotalTimeToComplete: float = 0
  AverageTimeToProcessEachDocument: float = 0.0
  DocumentsProcessed: int = 0
  NumberOfDocumentsToProcess: int = 0
  CollectionName: str = ''
  IngestedResponseObjects: list[Any] = field(default_factory=list[Any])


class DocumentIngestionPipeline:
  def __init__(
    self,
    minio: MinIO_Object,
    typesense: Typesense_Object,
    serverResponse: ServerResponseV2,
  ) -> None:
    self.minio = minio
    self.typesense = typesense
    self.serverResponse = serverResponse
    self.ingestionProcessors: list[IDocumentIngestor] = []
    self.pipelineResponseObjects: list[DocumentIngestionResponseObject] = []

  async def Run(
    self, documentCollectionBucket: str, schemaName: str
  ) -> AsyncGenerator[ServerResponseObject, Any]:
    self.ingestionProcessors = []
    self.pipelineResponseObjects = []
    self.__InitDocumentIngestors()
    currentResponse: DocumentIngestionPipelineResponseObject = (
      DocumentIngestionPipelineResponseObject()
    )
    currentResponse.NumberOfDocumentsToProcess = (
      self.minio.GetNumberOfObjectsInBucket(documentCollectionBucket)
    )
    currentResponse.Message = 'Indexing'
    startTime = time.time() * 1000
    currentResponse.CollectionName = schemaName
    yield self.serverResponse.GenerateServerResponse(currentResponse)
    for document in self.minio.GetObjectsInBucket(documentCollectionBucket):
      currentResponse.DocumentsProcessed += 1
      if document.object_name is None:
        continue
      for i in range(0, len(self.ingestionProcessors)):
        result = await self.ingestionProcessors[i].IndexDocument(
          document.object_name,
          cast(
            dict[str, str],
            (
              await self.minio.GetContentOfBucketObject(
                documentCollectionBucket, document.object_name
              ).Data['content']
            ),
          ),
          schemaName,
        )

        self.pipelineResponseObjects[i].Statistics.append(
          result[2] if result[1] else StatisticObject('error', -1)
        )

    print(self.pipelineResponseObjects)
    currentResponse.TotalTimeToComplete = (time.time() * 1000) - startTime
    currentResponse.AverageTimeToProcessEachDocument = (
      currentResponse.TotalTimeToComplete
      / currentResponse.NumberOfDocumentsToProcess
    )
    currentResponse.Message = 'Finished!'
    currentResponse.Finished = True
    currentResponse.Success = True
    yield self.serverResponse.GenerateServerResponse(currentResponse)

  def __InitDocumentIngestors(self):
    self.AddDocumentIngestor(
      SimpleDocumentIngestion(self.minio, self.typesense, self.serverResponse),
      'simple-ingestor',
    )

  def AddDocumentIngestor(
    self, documentIngestor: IDocumentIngestor, ingestorName: str
  ):
    self.ingestionProcessors.append(documentIngestor)
    self.pipelineResponseObjects.append(
      DocumentIngestionResponseObject(ingestorName)
    )
