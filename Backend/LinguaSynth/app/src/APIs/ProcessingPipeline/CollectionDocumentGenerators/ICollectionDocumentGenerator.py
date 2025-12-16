import time
from dataclasses import dataclass, field
from APIs.UploadNewDocument import Uploader
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from typesense.types.document import DocumentSchema
from Utils.ServerResponse import ServerResponseV2


@dataclass
class StatisticsObject:
  DocumentName: str
  ProcessingTime: float


@dataclass
class CollectionDocumentGenerationResponseObject:
  ProcessName: str = 'placeholder'
  Statistics: list[StatisticsObject] = field(
    default_factory=list[StatisticsObject]
  )


class ICollectionDocumentGenerator:
  def __init__(
    self,
    minio: MinIO_Object,
    llm: LLM_Object,
    serverResponse: ServerResponseV2,
    targetBucket: str,
    collectionName: str,
    outputBucketName: str,
  ) -> None:
    self.minio = minio
    self.llm = llm
    self.targetBucket = targetBucket
    self.fileUploader = Uploader(
      minio, serverResponse, f'{outputBucketName}-documents'
    )
    self.collectionName = collectionName
    self.startTime: float = -1

  async def GenerateCollectionDocument(
    self,
    content: str,
    fileName: str,
    documentSchema: DocumentSchema,
  ) -> tuple[str, bool, StatisticsObject]:
    self.statisticsObject: StatisticsObject = StatisticsObject(
      fileName,
      0,
    )
    self.startTime = time.time() * 1000
    return (
      'placeholder',
      False,
      StatisticsObject('', 0),
    )
