from dataclasses import dataclass, field
from APIs.ProcessingPipeline.CollectionDocumentGenerators import (
  ANNClusteringDocumentGenerator as ScaNNGenerator,
  ENNCosineSimilarityDocumentGenerator as ENNCosineSimilarityGenerator,
  SimpleCollectionDocumentGenerator as SimpleGenerator,
  EmbeddingCollectionDocumentGenerator as EmbeddingGenerator,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from APIs.ProcessingPipeline.CollectionDocumentGenerators.ICollectionDocumentGenerator import (
  ICollectionDocumentGenerator,
  CollectionDocumentGenerationResponseObject,
  StatisticsObject,
)
from Utils.ServerResponse import ServerResponseV2, ServerResponseObject
from typesense.types.document import DocumentSchema


@dataclass
class CollectionDocumentGenerationPipelineResponseObject(ServerResponseObject):
  TotalTimeToComplete: float = 0
  AverageTimeToProcessEachDocument: float = 0.0
  DocumentsProcessed: int = 0
  NumberOfDocumentsToProcess: int = 0
  CollectionName: str = ''
  IngestedResponseObjects: list[CollectionDocumentGenerationResponseObject] = (
    field(default_factory=list[CollectionDocumentGenerationResponseObject])
  )


class CollectionDocumentGenerationPipeline:
  def __init__(
    self,
    minio: MinIO_Object,
    llm: LLM_Object,
    serverResponse: ServerResponseV2,
    targetBucket: str,
    schemaName: str,
  ) -> None:
    self.ingestionProcessors: list[ICollectionDocumentGenerator] = []
    self.minio = minio
    self.llm = llm
    self.pipelineResponseObject: list[
      CollectionDocumentGenerationResponseObject
    ] = []
    self.serverResponse = serverResponse
    self.targetBucket = targetBucket
    self.collectionName = schemaName
    self.serverResponse

    self.__InitIngestionMethods()

  def __InitIngestionMethods(self):
    self.AddIngestionProcessor(
      SimpleGenerator.SimpleCollectionDocumentGenerator(
        self.minio,
        self.llm,
        self.serverResponse,
        self.targetBucket,
        self.collectionName,
        'rule-based-document-generation',
      ),
      'rule-based-document-generation',
    )
    self.AddIngestionProcessor(
      ENNCosineSimilarityGenerator.ENNCosineSimilarity(
        self.minio,
        self.llm,
        self.serverResponse,
        self.targetBucket,
        self.collectionName,
        'enn-cosine-similarity-based-document-generation',
      ),
      'enn-cosine-similarity-based-document-generation',
    )
    self.AddIngestionProcessor(
      ScaNNGenerator.ANNClustering(
        self.minio,
        self.llm,
        self.serverResponse,
        self.targetBucket,
        self.collectionName,
        'scann-based-document-generation',
      ),
      'scann-based-document-generation',
    )

  def AddIngestionProcessor(
    self, ingestor: ICollectionDocumentGenerator, ingestorName: str
  ):
    self.ingestionProcessors.append(ingestor)
    self.pipelineResponseObject.append(
      CollectionDocumentGenerationResponseObject(ingestorName)
    )

  async def Run(
    self,
    content: str,
    fileName: str,
    documentSchema: DocumentSchema,
    collectionName: str,
  ) -> tuple[list[CollectionDocumentGenerationResponseObject], bool]:
    for i in range(0, len(self.ingestionProcessors)):
      response = await self.ingestionProcessors[i].GenerateCollectionDocument(
        content, fileName, documentSchema
      )
      self.pipelineResponseObject[i].Statistics.append(
        response[2] if response[1] else StatisticsObject('error', -1)
      )

    return self.pipelineResponseObject, True
