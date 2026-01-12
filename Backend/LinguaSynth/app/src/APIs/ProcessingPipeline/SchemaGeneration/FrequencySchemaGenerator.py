import json
import time
from typing import Any, cast, override
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from APIs.ProcessingPipeline.SchemaGeneration.ISchemaGenerator import (
  ISchemaGenerator,
  StatisticsObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2


class FrequencyDrivenSchemaGenerator(ISchemaGenerator):
  @override
  def __init__(
    self,
    minio: MinIO_Object,
    uploadServerResponse: ServerResponseV2,
    generatorName: str,
    wordFrequency: float = 0.7,
  ) -> None:
    super().__init__(minio, uploadServerResponse, generatorName)
    self.wordFrequency = wordFrequency

  async def GenerateSchema(
    self, keywords: list[str], targetBucketName: str
  ) -> tuple[str, bool, StatisticsObject]:
    await super().GenerateSchema(keywords, targetBucketName)
    startTime = time.time() * 1000
    selectedKeywords: list[tuple[str, float]] = self.SelectCandidateFields(
      keywords
    )
    self.statisticsObject.selectedKeywords = [
      word[0] for word in selectedKeywords
    ]
    self.statisticsObject.selectedKeywordsCount = len(selectedKeywords)

    schemaName: str = self.GenerateSchemaName(selectedKeywords)
    self.statisticsObject.newSchemaName = schemaName

    generatedSchema: dict = self.GenerateFinalSchema(
      self.statisticsObject.selectedKeywords, schemaName
    )

    # Upload the processed file to Minio
    schemaAsJson = json.dumps(generatedSchema)
    uploadResult = await self.fileUploader.UploadDocumentContentAsFile(
      schemaAsJson,
      f'{targetBucketName}-{schemaName}.txt',
    )

    # calculate the statistics for the process.
    self.statisticsObject.ProcessingTime = (time.time() * 1000) - startTime
    return uploadResult.Message, uploadResult.Success, self.statisticsObject

  def SelectCandidateFields(
    self, keywords: list[str]
  ) -> list[tuple[str, float]]:
    selectedKeywords: list[tuple[str, float]] = []
    content: str = '.\n'.join(keywords)
    selectedKeywords = self.ExtractKeywords(content, self.wordFrequency)
    selectedKeywords = list(dict.fromkeys(selectedKeywords))
    return selectedKeywords

  def GenerateSchemaName(
    self, keywords: list[tuple[str, float]], minFrequency: float = 0.95
  ) -> str:
    selectedKeywords = []
    for word in keywords:
      if word[1] > minFrequency:
        selectedKeywords.append(word[0])

    name = (
      str(selectedKeywords)
      .lower()
      .replace(' ', '-')
      .replace(',', '')
      .replace("'", '')
    )
    return name

  def GenerateFinalSchema(
    self, keywords: list[str], schemaName: str
  ) -> dict[str, Any]:
    return self.__BuildTypesenseSchema(schemaName, keywords)

  def ExtractKeywords(
    self, content: str, frequency: float, minDF: float = 3
  ) -> list[tuple[str, float]]:
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
    extractedKeywords: list[tuple[str, float]] = []
    for tup in tfidfVector:
      wordFrequency = cast(float, tup[2])
      if wordFrequency > frequency:
        word = str(features[tup[1]])
        extractedKeywords.append((word, wordFrequency))
      # print('\n', features[tup[1]], tup[2])

    return extractedKeywords
