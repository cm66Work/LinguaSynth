import json
import time
import re
from typing import Any, Optional, cast, override
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from APIs.ProcessingPipeline.SchemaGeneration.ISchemaGenerator import (
  ISchemaGenerator,
  StatisticsObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2

NUMERIC_LIKE_TERMS = [
  # identifiers
  'id',
  'code',
  'number',
  'num',
  'index',
  'ref',
  'reference',
  'key',
  # counts / sizes
  'count',
  'total',
  'amount',
  'quantity',
  'qty',
  'size',
  'length',
  'width',
  'height',
  'depth',
  'volume',
  'capacity',
  # financial
  'price',
  'cost',
  'value',
  'amount',
  'balance',
  'rate',
  'fee',
  'tax',
  'salary',
  'wage',
  # versioning / ordering
  'version',
  'revision',
  'rev',
  'level',
  'rank',
  # metrics
  'score',
  'rating',
  'points',
  'weight',
  'mass',
  'speed',
  # time-like but numeric (not dates)
  'duration',
  'interval',
  'period',
  'year',
  'years',
  'age',
  # other useful technical numeric fields
  'limit',
  'range',
  'threshold',
  'index',
  'step',
  'iteration',
]
DATE_LIKE_TERMS = [
  'date',
  'day',
  'month',
  'year',
  'datetime',
  'timestamp',
  'time',
  'created',
  'creation',
  'created_on',
  'modified',
  'updated',
  'update',
  'published',
  'posted',
  'start',
  'start_date',
  'end',
  'end_date',
  'begin',
  'begin_date',
  'expiry',
  'expires',
  'expiration',
  'deadline',
  'due',
  'issued',
  'issue_date',
  'effective',
  'effective_date',
  'released',
  'release_date',
]


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
    # calculate the statistics for the process.
    self.statisticsObject.EndTime = time.time() * 1000
    self.statisticsObject.ProcessingTime = (
      self.statisticsObject.EndTime - self.statisticsObject.StartTime
    )

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

    return uploadResult.Message, uploadResult.Success, self.statisticsObject

  def SelectCandidateFields(
    self, keywords: list[str]
  ) -> list[tuple[str, float]]:
    selectedKeywords: list[tuple[str, float]] = []
    # TODO:: select the highest frequency key words.
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

  def __ToFieldName(self, keyword: str) -> str:
    name = keyword.strip().lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = name.strip('_')
    if not name:
      name = 'field'
    return name

  def __InferFieldType(self, keyword: str) -> str:
    k = keyword.lower()
    tokens = re.split(r'[^a-z0-9]+', k)
    if any(tok in NUMERIC_LIKE_TERMS for tok in tokens):
      return 'int32'
    if any(tok in DATE_LIKE_TERMS for tok in tokens):
      return 'init32'
    return 'string'

  def __BuildTypesenseSchema(
    self,
    collection_name: str,
    keywords: list[str],
    maxFields: Optional[int] = None,
  ) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    seenNames = set()

    for i, keyword in enumerate(keywords):
      if maxFields is not None and len(fields) >= maxFields:
        break
      raw = keyword.strip()
      if not raw:
        continue
      fieldName = self.__ToFieldName(raw)

      if fieldName in seenNames:
        continue
      if fieldName == 'id':
        # Typesense already uses "id" as the document identifier
        continue

      fieldType = self.__InferFieldType(raw)

      fieldDef: dict[str, Any] = {'name': fieldName, 'type': fieldType}

      fields.append(fieldDef)
      seenNames.add(fieldName)

    defaultSortingField = None
    for f in fields:
      if f['type'] in ('int32', 'float'):
        defaultSortingField = f['name']
        break

    schema: dict[str, Any] = {'name': collection_name[1:-1], 'fields': fields}

    if defaultSortingField is not None:
      schema['default_sorting_field'] = defaultSortingField
    return schema

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
