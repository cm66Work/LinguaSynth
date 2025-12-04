from dataclasses import dataclass, field
from ObjectInterfaces.MinIO_Object import MinIO_Object
from APIs.UploadNewDocument import Uploader
from Utils.ServerResponse import ServerResponseV2


@dataclass
class StatisticsObject:
  DocumentName: str
  StartTime: float
  EndTime: float
  ProcessingTime: float
  FileSizeBefore: float
  FileSizeAfter: float


@dataclass
class DocumentResponseObject:
  ProcessName: str = 'placeholder'
  Statistics: list[StatisticsObject] = field(
    default_factory=list[StatisticsObject]
  )


class IDocumentProcessor:
  def __init__(
    self,
    minio: MinIO_Object,
    uploadServerResponse: ServerResponseV2,
    bucketName: str,
  ):
    self.minio = minio
    self.fileUploader = Uploader(minio, uploadServerResponse, bucketName)

  async def ProcessDocument(
    self,
    content: str,
    fileName: str,
  ) -> tuple[str, bool, StatisticsObject]:
    return 'placeholder', False, StatisticsObject('', 0, 0, 0, 0, 0)
