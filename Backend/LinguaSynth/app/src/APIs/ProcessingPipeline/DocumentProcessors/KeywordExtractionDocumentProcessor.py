from sys import getsizeof
import time
from typing import override
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from APIs.ProcessingPipeline.DocumentProcessors.IDocumentProcessor import (
  IDocumentProcessor,
  StatisticsObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
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
    await super().ProcessDocument(content, fileName)
    # Extract the keywords form the current document.
    extractedKeywords = self.ExtractKeywords(content, self.wordFrequency)

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

  def ExtractKeywords(
    self, content: str, frequency: float, minDF: float = 2
  ) -> list[str]:
    """
    Extracts the top keywords from the given content.
    Args:
        content (str): The content to extract the keywords from.
        frequency (float): Controls how often a keyword has to be present in the content before it is selected.

    Returns:
        list (list[str]): list of all extracted keywords from the content that appear a number of times equal too or more than the frequency.
    """
    countVectorizer = CountVectorizer(
      stop_words='english', max_df=frequency, min_df=minDF
    )
    paragraphs = [
      paragraphs.strip()
      for paragraphs in content.split('\n')
      if len(paragraphs) > 0
    ]

    wordCount = countVectorizer.fit_transform(paragraphs)
    features = countVectorizer.get_feature_names_out()

    transformer = TfidfTransformer()
    transformer.fit(wordCount)

    countVector = countVectorizer.transform(paragraphs)
    tfidfVector = (transformer.transform(countVector)).tocoo()  # type: ignore
    tuples = zip(tfidfVector.row, tfidfVector.col, tfidfVector.data)

    tfidfVector = sorted(tuples, key=lambda x: x[2], reverse=True)
    extractedKeywords: list[str] = []
    for tup in tfidfVector:
      if tup[2] > frequency:
        extractedKeywords.append(str(features[tup[1]]))
      # print('\n', features[tup[1]], tup[2])

    return extractedKeywords
