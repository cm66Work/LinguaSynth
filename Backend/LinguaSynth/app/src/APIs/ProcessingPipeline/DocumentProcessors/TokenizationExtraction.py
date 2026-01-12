import time
import nltk
from nltk.tokenize import word_tokenize
from sys import getsizeof
from typing import override
from APIs.ProcessingPipeline.DocumentProcessors.IDocumentProcessor import (
  IDocumentProcessor,
  StatisticsObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2


class TokenizationExtraction(IDocumentProcessor):
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
    nltk.download('punkt')

  async def ProcessDocument(
    self, content: str, fileName: str
  ) -> tuple[str, bool, StatisticsObject]:
    await super().ProcessDocument(content, fileName)
    startTime: float = time.time() * 1000

    tokens = word_tokenize(content)
    tokens = tokens[1:-1]
    # tokens = str(tokens).replace("'", '')
    tokens = ', '.join(tokens)

    # calculate the statistics for the process.
    self.statisticsObject.ProcessingTime = (time.time() * 1000) - startTime
    self.statisticsObject.FileSizeAfter = getsizeof(tokens)

    # Upload the processed file to Minio
    uploadResult = await self.fileUploader.UploadDocumentContentAsFile(
      tokens, fileName
    )

    return uploadResult.Message, uploadResult.Success, self.statisticsObject
