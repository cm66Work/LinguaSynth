import time
from yake import KeywordExtractor
from sys import getsizeof
from typing import override
from APIs.ProcessingPipeline.DocumentProcessors.IDocumentProcessor import (
  IDocumentProcessor,
  StatisticsObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2


class YAKEExtraction(IDocumentProcessor):
  @override
  def __init__(
    self,
    minio: MinIO_Object,
    serverResponse: ServerResponseV2,
    bucketName: str,
    wordFrequency: float = 0.45,
  ):
    super().__init__(minio, serverResponse, bucketName)
    self.wordFrequency = wordFrequency

  async def ProcessDocument(
    self, content: str, fileName: str
  ) -> tuple[str, bool, StatisticsObject]:
    await super().ProcessDocument(content, fileName)
    startTime: float = time.time() * 1000

    # run the RAKE
    extractedKeywords = str(self.YAKE(content))[1:-1].replace("'", '')
    # print(f'\n extracted keywords: {len(extractedKeywords)} \n')

    if len(extractedKeywords) > 0:
      # calculate the statistics for the process.
      self.statisticsObject.ProcessingTime = (time.time() * 1000) - startTime
      self.statisticsObject.FileSizeAfter = getsizeof(extractedKeywords)

      # Upload the processed file to Minio
      uploadResult = await self.fileUploader.UploadDocumentContentAsFile(
        extractedKeywords, fileName
      )

      return uploadResult.Message, uploadResult.Success, self.statisticsObject
    return f'Error:Failed to parse: {fileName}', False, self.statisticsObject

  def YAKE(self, content: str):
    keywordExtractor = KeywordExtractor()
    extractedWords: list[str] = []
    for keyword, rating in keywordExtractor.extract_keywords(content):
      rating = rating * 10
      if rating > 1:
        rating = 1
      # print(f'keyword: {keyword}, rating: {rating}\n')
      if rating > self.wordFrequency:
        extractedWords.append(keyword)

    return extractedWords
