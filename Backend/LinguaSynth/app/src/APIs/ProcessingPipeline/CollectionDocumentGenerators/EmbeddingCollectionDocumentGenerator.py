from dataclasses import dataclass
import math
import re
import time
from typing import cast, override
from APIs.ProcessingPipeline.CollectionDocumentGenerators.ICollectionDocumentGenerator import (
  ICollectionDocumentGenerator,
  StatisticsObject,
)
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2
from typesense.types.document import DocumentSchema

Vector = list[float]


@dataclass
class DocumentTemplate:
  fieldName: str
  fieldPhrase: str = (
    ''  # The current phrase that is the closest im similarity to the fieldName.
  )
  similarityScore: float = (
    0.01  # The score of how close the field Phrase is to the field Name.
  )
  # This value is at 0.01 because we still want the possibility for the field phrase to be empty.


class ENNCollectionDocumentGenerator(ICollectionDocumentGenerator):
  """
  Exact Nearest Neighbor between each document collection field name and the data inside the given document.

  Running GenerateCollectionDocument will upload a Typesense document to a minio bucket for later ingestion into typesense.

  This process does produce a lot of junk information inside the generated document. So it leans heavily on Typesense's ability to perform fuzzy searching and partial matching
  """

  @override
  def __init__(
    self,
    minio: MinIO_Object,
    llm: LLM_Object,
    serverResponse: ServerResponseV2,
    targetBucket: str,
    collectionName: str,
    outputBucketName: str,
  ) -> None:
    super().__init__(
      minio, llm, serverResponse, targetBucket, collectionName, outputBucketName
    )

  async def GenerateCollectionDocument(
    self,
    content: str,
    fileName: str,
    documentSchema: DocumentSchema,
  ) -> tuple[str, bool, StatisticsObject]:
    await super().GenerateCollectionDocument(content, fileName, documentSchema)

    cleanContent = self.__CleanInputContent(content, fileName)
    mapped = await self.__MapPhrasesToFields(documentSchema, cleanContent)
    mapped['id'] = fileName

    uploadResult = await self.fileUploader.UploadDocumentContentAsFile(
      str(mapped), fileName
    )

    self.statisticsObject.ProcessingTime = (time.time() * 1000) - self.startTime
    return uploadResult.Message, uploadResult.Success, self.statisticsObject

  def __CleanInputContent(self, content: str, fileName: str) -> str:
    """
    Remove an exact line match of the fileName so it does not dominate matching.

    :param self: Description
    :param content: Description
    :type content: str
    :param fileName: Description
    :type fileName: str
    :return: Description
    :rtype: str
    """
    lines = [line for line in content.splitlines() if line != fileName]
    return ' '.join(lines).strip()

  async def __MapPhrasesToFields(
    self,
    documentSchema: DocumentSchema,
    contentDocument: str,
    sentenceSplit: int = 2,  # How many parts should a sentence be split into.
  ) -> dict[str, str]:
    """
    Embedding based mapping from phrases to document schema

    Args
        documentSchema (DocumentSchema): The schema for the document
        fieldHints (dict[str, list[str]]): Hard coded mappings, eg. {quality:['qa', 'assurance']}
    """
    # Not trying to over complicate things right now. We just want to find out which sentence best matches the field name. Typesense will do the searching, will return the file even if it is a partial match.
    # splitSentences = self.__SplitSentences(contentDocument, sentenceSplit)
    splitSentences = contentDocument

    mergedWords: list[str] = []
    mergedWords.extend(splitSentences)
    mergedWords.extend(documentSchema.keys())

    mergeEmbeddings = await self.__GenerateKeywordEmbeddings(mergedWords)

    fieldNameEmbeddings: dict[str, Vector] = {}
    contentEmbeddings: dict[str, Vector] = {}

    schemaKeys = set(documentSchema.keys())
    sentenceKeys = set(splitSentences)

    for word, vec in mergeEmbeddings.items():
      normVec = self.__Normalize(cast(Vector, vec))
      if word in schemaKeys:
        fieldNameEmbeddings[word]
      elif word in sentenceKeys:
        contentEmbeddings[word] = normVec

    templates: list[DocumentTemplate] = []
    for fieldName, fieldVec in fieldNameEmbeddings.items():
      best = DocumentTemplate(fieldName=fieldName)

      for phrase, phraseVec in contentEmbeddings.items():
        score = self.__CosineSimilarity(fieldVec, phraseVec) * 100
        if score > best.similarityScore:
          best.fieldPhrase = self.__CleanString(phrase)
          best.similarityScore = score

      templates.append(best)

    print(f'templates: {templates}')

    return {t.fieldName: t.fieldPhrase for t in templates}

  def __SplitSentences(self, content: str, sentenceSplit: int) -> list[str]:
    # Extract sentences ending in . ! ? and keep punctuation.
    sentences = re.compile(r'[^\s].*?[.!?](?=\s|$)').findall(content)

    pieces: list[str] = []
    for sentence in sentences:
      if not sentence:
        continue

      start = 0
      length = len(sentence)
      for i in range(max(1, sentenceSplit)):
        end = (
          start
          + length // sentenceSplit
          + (1 if i < (length % sentenceSplit) else 0)
        )
        pieces.append(sentence[start:end])
        start = end

    return [p.strip() for p in pieces if p.strip()]

  async def __GenerateKeywordEmbeddings(
    self, keywords: list[str], k: int = 25
  ) -> dict[str, Vector]:
    embeddings = await self.llm.GetEmbeddingsForContent(keywords)
    return dict(zip(keywords, cast(list[Vector], embeddings)))

  def __Normalize(self, v):
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v] if norm else v

  def __CosineSimilarity(self, a, b) -> float:
    return sum(x * y for x, y in zip(a, b))

  def __CleanString(self, phrase: str) -> str:
    """
    Convert a phrase into a safe Typesense-ish field value.
    Example: "Creation Date" -> "creation date"
    """
    phrase = re.sub(r'[()\[\]{}\"\.]', '', phrase)
    phrase = re.sub(r'\s+', ' ', phrase).strip().lower()

    allowed = set('abcdefghijklmnopqrstuvwxyz0123456789_ ')
    return ''.join(ch for ch in phrase if ch in allowed)
