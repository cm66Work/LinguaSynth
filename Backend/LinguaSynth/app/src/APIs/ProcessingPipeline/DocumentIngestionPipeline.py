import time
import ast
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
  TotalRunTime: float = 0
  TotalTimeDividedByDocuments: float = 0.0
  NumberOfProcessedDocuments: int = 0
  TotalNumberOfProcessedDocuments: int = 0
  CollectionBeingIngestedInto: str = ''
  ResponseObjects: list[Any] = field(default_factory=list[Any])


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
    currentResponse.TotalNumberOfProcessedDocuments = (
      self.minio.GetNumberOfObjectsInBucket(documentCollectionBucket)
    )
    currentResponse.Message = 'Indexing'
    startTime = time.time() * 1000
    currentResponse.CollectionBeingIngestedInto = schemaName
    yield self.serverResponse.GenerateServerResponse(currentResponse)
    totalNumDocs: int = self.minio.GetNumberOfObjectsInBucket(
      documentCollectionBucket
    )
    processedNumDocs: int = 0
    for document in self.minio.GetObjectsInBucket(documentCollectionBucket):
      currentResponse.NumberOfProcessedDocuments += 1
      if document.object_name is None:
        continue
      for i in range(0, len(self.ingestionProcessors)):
        documentContent: dict[str, str] = ast.literal_eval(
          self.minio.GetContentOfBucketObject(
            documentCollectionBucket, document.object_name
          ).Data['content']
        )
        result = await self.ingestionProcessors[i].IndexDocument(
          document.object_name,
          documentContent,
          schemaName,
        )
        processedNumDocs += 1

        self.pipelineResponseObjects[i].Statistics.append(
          result[2] if result[1] else StatisticObject(f'error: {result[0]}', -1)
        )
      print(f'indexed {processedNumDocs}/{totalNumDocs}')

    currentResponse.TotalRunTime = (time.time() * 1000) - startTime
    currentResponse.TotalTimeDividedByDocuments = (
      currentResponse.TotalRunTime
      / currentResponse.TotalNumberOfProcessedDocuments
    )
    currentResponse.Message = 'Finished!'
    currentResponse.Finished = True
    currentResponse.Success = True
    currentResponse.ResponseObjects = self.pipelineResponseObjects
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
