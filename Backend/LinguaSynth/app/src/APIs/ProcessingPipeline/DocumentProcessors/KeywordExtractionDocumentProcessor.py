from sys import getsizeof
import time
from typing import override
from APIs.ProcessingPipeline.DocumentProcessors.IDocumentProcessor import (
  IDocumentProcessor,
  StatisticsObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.DocumentHelpers import DocumentHelper
from Utils.ServerResponse import ServerResponseV2


class KeywordExtractionDocumentProcessor(IDocumentProcessor):
  @override
  def __init__(
    self,
    minio: MinIO_Object,
    serverResponse: ServerResponseV2,
    bucketName: str,
    wordFrequency: float = 0.3,
  ):
    super().__init__(minio, serverResponse, bucketName)
    self.wordFrequency = wordFrequency

  async def ProcessDocument(
    self,
    content: str,
    fileName: str,
  ) -> tuple[str, bool, StatisticsObject]:
    self.fileName = fileName
    self.statisticsObject: StatisticsObject = StatisticsObject(
      fileName, time.time() * 1000, -1, -1, getsizeof(content), -1
    )

    # Extract the keywords form the current document.
    extractedKeywords = DocumentHelper.ExtractKeywords(
      content, self.wordFrequency
    )

    extractedKeywords = str(extractedKeywords)[1:-1].replace("'", '')

    # calculate the statistics for the process.
    self.statisticsObject.EndTime = time.time() * 1000
    self.statisticsObject.ProcessingTime = (
      self.statisticsObject.EndTime - self.statisticsObject.StartTime
    )
    self.statisticsObject.FileSizeAfter = getsizeof(extractedKeywords)

    # Upload the processed file to Minio
    uploadResult = await self.fileUploader.UploadDocumentContentAsFile(
      extractedKeywords, fileName
    )

    return uploadResult.Message, uploadResult.Success, self.statisticsObject
