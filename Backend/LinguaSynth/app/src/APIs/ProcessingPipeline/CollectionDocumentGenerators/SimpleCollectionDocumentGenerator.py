import re
import time
from typing import override
from APIs.ProcessingPipeline.CollectionDocumentGenerators.ICollectionDocumentGenerator import (
  ICollectionDocumentGenerator,
  StatisticsObject,
)
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2
from typesense.types.document import DocumentSchema


class SimpleCollectionDocumentGenerator(ICollectionDocumentGenerator):
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
    mapped = self.__MapPhrasesToFields(documentSchema, content)
    mapped['id'] = fileName

    # Upload the mapped document to its bucket so we dont have to map it again.
    uploadResult = await self.fileUploader.UploadDocumentContentAsFile(
      str(mapped), fileName
    )

    self.statisticsObject.ProcessingTime = (time.time() * 1000) - self.startTime
    return uploadResult.Message, uploadResult.Success, self.statisticsObject

  def __Tokens(self, text: str) -> list[str]:
    return self.__Normalize(text).split()

  def __ScoreMatches(self, field: str, phrase: str) -> int:
    """
    Rule based scoring:
    - Exact match is best
    - Whole-word containment is next
    - Substring containment is last
    """

    field = self.__Normalize(field)
    phrase = self.__Normalize(phrase)

    if not field or not phrase:
      return 0
    if field == phrase:
      return 100

    fieldTokens = set(self.__Tokens(field))
    phraseTokens = set(self.__Tokens(phrase))

    # Whole word overlap
    overlap = len(fieldTokens & phraseTokens)
    if overlap:
      return 50 + overlap * 10 - max(0, len(phraseTokens) - len(fieldTokens))

    # fallback substring
    if field in phrase or phrase in field:
      # phrase contains the field, or field contains the phrase
      return 10  # <-- magic number
    return 0

  def __MapPhrasesToFields(
    self,
    documentSchema: DocumentSchema,
    content: str,
    joinMultiple: bool = True,
    separator: str = '|',
    defaultValue: str = '',
  ) -> dict[str, str]:
    """
    Maps phrases to the document schema fields.

    Args:
        documentSchema (DocumentSchema): typesense DocumentSchema
        content (str): The content from the file.
        joinMultiple: (bool): Merge matching phrases into one string per field.
    """
    phrases = self.__SplitPhrases(content)

    result: dict[str, str] = {
      field: defaultValue for field in documentSchema.keys()
    }

    for field in documentSchema.keys():
      scored: list[tuple[int, str]] = []
      for phrase in phrases:
        s = self.__ScoreMatches(field, phrase)
        if s > 0:
          scored.append((s, phrase))
      if not scored:
        continue  # no phrases match this field
      scored.sort(
        key=lambda x: x[0], reverse=True
      )  # get the best matching phrase to the filed

      if field[-1:-2] == '[]':
        # keep phrases in score order, de-duplicate by normalized form
        seen = set()
        chosen = []
        for _, ph in scored:
          key = self.__Normalize(ph)
          if key in seen:
            continue  # duplicate
          seen.add(key)
          chosen.append(ph)
        result[field] = separator.join(chosen)
      else:
        result[field] = scored[0][1]
    return result

  def __SplitPhrases(self, content: str) -> list[str]:
    parts = [p.strip() for p in content.split(',')]
    return [p for p in parts if p]

  def __Normalize(self, text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]+', '', text)
    text = re.sub(r'\s+', '', text).strip()
    return text
