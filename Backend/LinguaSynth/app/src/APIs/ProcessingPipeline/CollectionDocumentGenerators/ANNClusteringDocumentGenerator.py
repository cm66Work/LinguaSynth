from dataclasses import dataclass
import json
import re
import time
import math
import numpy as np
from typing import cast, override
from APIs.ProcessingPipeline.CollectionDocumentGenerators.ICollectionDocumentGenerator import (
  ICollectionDocumentGenerator,
  StatisticsObject,
)
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2
from pydantic import conint
from typesense.types.document import DocumentSchema
from sklearn.preprocessing import normalize
from sklearn.cluster import MiniBatchKMeans
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


# Option B only helps when you have lots of documents (hundreds of thousands or more). With tiny n_docs, it fails (as you saw) and even if it ran, it would not improve anything. But since wer are keeping this small then we will never need anything this advanced.
class ANNClustering(ICollectionDocumentGenerator):
  """
  Approximate Nearest Neighbor search with ScaNN, using cosine similarity, to map the information in the given document to the given document schema field names.

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
    minFrequency: float = 0.4,
  ) -> None:
    super().__init__(
      minio, llm, serverResponse, targetBucket, collectionName, outputBucketName
    )
    self.minFrequency = minFrequency

  async def GenerateCollectionDocument(
    self,
    content: str,
    fileName: str,
    documentSchema: DocumentSchema,
  ) -> tuple[str, bool, StatisticsObject]:
    await super().GenerateCollectionDocument(content, fileName, documentSchema)

    # ContentEmbedding: (numberOfContent, dim)
    cleanContent = self.__SplitSentences(content, 1)
    contentEmbeddings = await self.__GenerateKeywordEmbeddings(cleanContent)
    contentArray = np.array(list(contentEmbeddings.values()), dtype=np.float32)
    contentArray = normalize(contentArray, axis=1)

    # KeywordEmbedding: (numberOfKeywords, dim)
    keywordContent = [doc for doc in documentSchema.keys()]
    keywordEmbeddings = await self.__GenerateKeywordEmbeddings(keywordContent)
    keywordsArray = np.array(list(keywordEmbeddings.values()), dtype=np.float32)
    keywordsArray = normalize(keywordsArray, axis=1)

    numClusters = min(512, contentArray.shape[0])
    numClusters = max(2, numClusters) if contentArray.shape[0] >= 2 else 1

    kmeans = MiniBatchKMeans(
      n_clusters=numClusters, batch_size=4096, random_state=0
    )
    labels = kmeans.fit_predict(contentArray)
    centroids = normalize(kmeans.cluster_centers_, axis=1)

    clustersToContent = [np.where(labels == c)[0] for c in range(numClusters)]

    n = contentArray.shape[0]

    centroidSims = cosine_similarity(keywordsArray, centroids)
    clustersPerQuery = centroidSims.shape[1]
    topClusters = np.argpartition(-centroidSims, clustersPerQuery - 1, axis=1)[
      :, :clustersPerQuery
    ]

    results = []
    for qi in range(keywordsArray.shape[0]):
      candIdX = np.concatenate([clustersToContent[c] for c in topClusters[qi]])
      candVec = contentArray[candIdX]
      sims = candVec @ keywordsArray[qi]
      k = min(n, sims.size)
      best = np.argpartition(-sims, k - 1)[:k]
      bestScored = best[np.argsort(-sims[best])]
      results.append((candIdX[bestScored], sims[bestScored]))

    mapped: dict[str, str] = {}

    for kwIdx, conIndices in enumerate(results):
      word = ''
      wordId = conIndices[0][-1]
      similarityScore = conIndices[1][-1]
      if similarityScore >= self.minFrequency:
        word = cleanContent[wordId]
      mapped[keywordContent[kwIdx]] = word

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
