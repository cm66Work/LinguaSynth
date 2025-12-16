import time
from sys import getsizeof
from typing import override
from APIs.ProcessingPipeline.DocumentProcessors.IDocumentProcessor import (
  IDocumentProcessor,
  StatisticsObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2


class RawTextExtraction(IDocumentProcessor):
  @override
  def __init__(
    self,
    minio: MinIO_Object,
    serverResponse: ServerResponseV2,
    bucketName: str,
    wordFrequency: float = 5,
  ):
    super().__init__(minio, serverResponse, bucketName)
    self.wordFrequency = wordFrequency

  async def ProcessDocument(
    self, content: str, fileName: str
  ) -> tuple[str, bool, StatisticsObject]:
    await super().ProcessDocument(content, fileName)
    # calculate the statistics for the process.
    self.statisticsObject.EndTime = time.time() * 1000
    self.statisticsObject.ProcessingTime = (
      self.statisticsObject.EndTime - self.statisticsObject.StartTime
    )
    self.statisticsObject.FileSizeAfter = getsizeof(content)

    # Upload the processed file to Minio
    uploadResult = await self.fileUploader.UploadDocumentContentAsFile(
      content, fileName
    )

    return uploadResult.Message, uploadResult.Success, self.statisticsObject
