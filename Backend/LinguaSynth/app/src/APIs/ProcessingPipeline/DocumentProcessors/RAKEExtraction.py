import time
import nltk
from sys import getsizeof
from typing import override
from rake_nltk import Rake
from APIs.ProcessingPipeline.DocumentProcessors.IDocumentProcessor import (
  IDocumentProcessor,
  StatisticsObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2


class RAKEExtraction(IDocumentProcessor):
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
    nltk.download('punkt_tab')
    nltk.download('stopwords')

  async def ProcessDocument(
    self, content: str, fileName: str
  ) -> tuple[str, bool, StatisticsObject]:
    await super().ProcessDocument(content, fileName)

    # run the RAKE
    extractedKeywords = str(self.RAKE(content))[1:-1].replace("'", '')
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

  def RAKE(self, content: str):
    rake = Rake()
    rake.extract_keywords_from_text(content)
    extractedWords: list[str] = []
    for rating, keyword in rake.get_ranked_phrases_with_scores():
      if rating > self.wordFrequency:
        extractedWords.append(keyword)

    return extractedWords
