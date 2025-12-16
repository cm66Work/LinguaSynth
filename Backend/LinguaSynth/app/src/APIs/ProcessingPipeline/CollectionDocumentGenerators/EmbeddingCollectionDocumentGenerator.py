import re
import time
import numpy as np
from typing import Optional, cast, override
from APIs.ProcessingPipeline.CollectionDocumentGenerators.ICollectionDocumentGenerator import (
  ICollectionDocumentGenerator,
  StatisticsObject,
)
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2
from typesense.types.document import DocumentSchema
from Utils.CosignSimilarity import MultiVector


class EmbeddingCollectionDocumentGenerator(ICollectionDocumentGenerator):
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
    mapped = await self.__MapPhrasesToFields(documentSchema, content)

    # Upload the mapped document to its bucket so we dont have to map it again.
    uploadResult = await self.fileUploader.UploadDocumentContentAsFile(
      str(mapped), fileName
    )

    self.statisticsObject.ProcessingTime = (time.time() * 1000) - self.startTime
    return uploadResult.Message, uploadResult.Success, self.statisticsObject

  async def __MapPhrasesToFields(
    self,
    documentSchema: DocumentSchema,
    content: str,
    topK: int = 3,
    threshold: float = 0.35,
    joinMultiple: bool = True,
    separator: str = '|',
    defaultValue: str = '',
    fieldHints: Optional[dict[str, list[str]]] = None,
  ) -> dict[str, str]:
    """
    Embedding based mapping from phrases to document schema

    Args
        documentSchema (DocumentSchema): The schema for the document
        fieldHints (dict[str, list[str]]): Hard coded mappings, eg. {quality:['qa', 'assurance']}
    """
    phrases = self.__SplitPhrases(content)
    if not phrases:
      return {
        k: defaultValue for k in documentSchema.keys()
      }  # Nothing to index

    fieldNames = list(documentSchema.keys())
    hints = fieldHints or {}

    fieldText = []
    for f in fieldNames:
      extras = hints.get(f, [])
      fieldText.append(self.__Normalize(''.join([f] + extras)))

    phrasesNormalized: list[str] = []
    for phrase in [self.__Normalize(p) for p in phrases]:
      if len(phrase) > 0:
        phrasesNormalized.append(phrase)

    phrasesEmbed = await self.llm.GetEmbeddingsForContent(phrasesNormalized)
    phrasesEmbed = cast(np.ndarray, phrasesEmbed)
    fieldEmbed = await self.llm.GetEmbeddingsForContent(fieldText)
    fieldEmbed = cast(np.ndarray, fieldEmbed)

    similarityMatrix = MultiVector(fieldEmbed, phrasesEmbed)

    result: dict[str, str] = {f: defaultValue for f in fieldNames}

    for fieldIdx, field in enumerate(fieldNames):
      sims = similarityMatrix[fieldIdx]  # type: ignore

      ranked = sorted(
        [(float(score), phrases[i]) for i, score in enumerate(sims)],
        key=lambda x: x[0],
        reverse=True,
      )

      filtered = [(s, p) for s, p in ranked if s >= threshold]
      if not filtered:
        continue

      if field[-1:-2] == '[]':
        result[field] = separator.join(p for _, p in filtered[:topK])
      else:
        result[field] = filtered[0][1]
    return result

  def __SplitPhrases(self, content: str) -> list[str]:
    parts = [p.strip() for p in content.split(',')]
    return [p for p in parts if p]

  def __Normalize(self, text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]+', '', text)
    text = re.sub(r'\s+', '', text).strip()
    return text
