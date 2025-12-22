import time
from dataclasses import dataclass, field
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.ServerResponse import ServerResponseV2


@dataclass
class StatisticObject:
  DocumentName: str
  ProcessingTime: float


@dataclass
class DocumentIngestionResponseObject:
  ProcessName: str = 'placeholder'
  Statistics: list[StatisticObject] = field(
    default_factory=list[StatisticObject]
  )


class IDocumentIngestor:
  def __init__(
    self,
    minio: MinIO_Object,
    typesense: Typesense_Object,
    serverResponse: ServerResponseV2,
  ) -> None:
    self.minio = minio
    self.typesense = typesense
    self.serverResponse = serverResponse

  async def IndexDocument(
    self, documentName: str, document: dict[str, str], collectionName: str
  ) -> tuple[str, bool, StatisticObject]:
    self.statisticsObject: StatisticObject = StatisticObject(documentName, -1)
    self.startTime = time.time() * 1000

    return 'placeholder', False, self.statisticsObject
