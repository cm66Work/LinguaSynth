import time
from dataclasses import dataclass, field
from ObjectInterfaces.MinIO_Object import MinIO_Object
from APIs.UploadNewDocument import Uploader
from Utils.ServerResponse import ServerResponseV2, ServerResponseObject


@dataclass
class StatisticsObject:
  targetSchemaName: str
  newSchemaName: str
  selectedKeywords: list[str]
  selectedKeywordsCount: int
  StartTime: float
  EndTime: float
  ProcessingTime: float


@dataclass
class GeneratorResponseObject(ServerResponseObject):
  ProcessName: str = 'placeholder'
  TotalDocumentsProcessed: int = 0
  CurrentDocumentsProcessed: int = 0
  Statistics: list[StatisticsObject] = field(
    default_factory=list[StatisticsObject]
  )


class ISchemaGenerator:
  PREFIX_SCHEMA_BUCKET_NAME: str = 'schemas'

  def __init__(
    self,
    minio: MinIO_Object,
    uploadServerResponse: ServerResponseV2,
    generatorName: str,
  ):
    self.minio = minio
    self.generatorName = generatorName
    self.fileUploader = Uploader(
      minio,
      uploadServerResponse,
      f'{self.PREFIX_SCHEMA_BUCKET_NAME}-{self.generatorName}',
    )

  async def GenerateSchema(
    self, keywords: list[str], targetBucketName: str
  ) -> tuple[str, bool, StatisticsObject]:
    self.statisticsObject: StatisticsObject = StatisticsObject(
      targetBucketName, 'default-schema-name', [], 0, time.time() * 1000, -1, -1
    )
    return (
      'placeholder',
      False,
      StatisticsObject('', 'default-schema-name', [], 0, 0, 0, 0),
    )
