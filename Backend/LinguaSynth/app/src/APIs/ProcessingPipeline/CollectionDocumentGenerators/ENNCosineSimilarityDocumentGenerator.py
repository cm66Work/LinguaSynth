from dataclasses import asdict, dataclass
import json
import math
import re
import time
import numpy as np
from typing import cast, override
from APIs.ProcessingPipeline.CollectionDocumentGenerators.ICollectionDocumentGenerator import (
  ICollectionDocumentGenerator,
  StatisticsObject,
)
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2
from typesense.types.document import DocumentSchema
from sklearn.metrics.pairwise import cosine_similarity


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


class ENNCosineSimilarity(ICollectionDocumentGenerator):
  """
  Exact Nearest Neighbor search to map the information in the given document to the given document schema field names.

  Makes use of SKlearn cosine similarity search to return exact matches. This process is slower but should produce higher accuracy.
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
    k: int = 5,
  ) -> tuple[str, bool, StatisticsObject]:
    await super().GenerateCollectionDocument(content, fileName, documentSchema)

    # ContentEmbedding: (numberOfContent, dim)
    cleanContent = self.__SplitSentences(content, 1)
    contentEmbeddings = await self.__GenerateKeywordEmbeddings(cleanContent)
    contentArray = np.array(list(contentEmbeddings.values()), dtype=np.float32)

    # KeywordEmbedding: (numberOfKeywords, dim)
    keywordContent = [doc for doc in documentSchema.keys()]
    keywordEmbeddings = await self.__GenerateKeywordEmbeddings(keywordContent)
    keywordArray = np.array(list(keywordEmbeddings.values()), dtype=np.float32)

    similarityMatrix = cosine_similarity(keywordArray, contentArray)

    topkIndices = np.argsort(similarityMatrix, axis=1)[:, -k:][:, ::-1]
    mapped: dict[str, str] = {}
    for kwIdX, docIndices in enumerate(topkIndices):
      for contentIdX in docIndices:
        mapped[keywordContent[kwIdX]] = cleanContent[contentIdX]

    mapped['id'] = fileName

    uploadResult = await self.fileUploader.UploadDocumentContentAsFile(
      json.dumps(mapped, indent=1), fileName
    )

    self.statisticsObject.ProcessingTime = (time.time() * 1000) - self.startTime
    return uploadResult.Message, uploadResult.Success, self.statisticsObject

  def __SplitSentences(self, content: str, sentenceSplit: int) -> list[str]:
    # Extract sentences ending in . ! ? and keep punctuation.
    sentences = ' '.join([sen.strip() for sen in content.splitlines()])
    sentences = re.compile(r'[^\s].*?[.!?](?=\s|$)').findall(sentences)
    return sentences

  async def __GenerateKeywordEmbeddings(
    self, keywords: list[str], k: int = 25
  ) -> dict[str, list[float]]:
    embeddings = await self.llm.GetEmbeddingsForContent(keywords)
    return dict(zip(keywords, cast(list[list[float]], embeddings)))
