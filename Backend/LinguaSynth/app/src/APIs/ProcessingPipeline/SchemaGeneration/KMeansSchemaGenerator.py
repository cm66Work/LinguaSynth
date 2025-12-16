import json
import time
from typing import Any, Optional, cast, override
from APIs.ProcessingPipeline.SchemaGeneration.ISchemaGenerator import (
  ISchemaGenerator,
  StatisticsObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from Utils.ServerResponse import ServerResponseV2
from sklearn.cluster import KMeans


class KMeansSchemaGenerator(ISchemaGenerator):
  @override
  def __init__(
    self,
    minio: MinIO_Object,
    uploadServerResponse: ServerResponseV2,
    generatorName: str,
    llm: LLM_Object,
    wordFrequency: float = 0.7,
    maxKeywords: int = 20,  # keep the top 20 best scoring groups for typesense fields.
  ):
    super().__init__(minio, uploadServerResponse, generatorName)
    self.wordFrequency = wordFrequency
    self.llm = llm
    self.maxNumberOfKeywords = maxKeywords

  async def GenerateSchema(
    self, keywords: list[str], targetBucketName: str
  ) -> tuple[str, bool, StatisticsObject]:
    await super().GenerateSchema(keywords, targetBucketName)
    self.statisticsObject.StartTime = time.time()

    keywordEmbeddings: dict[
      str, float
    ] = await self.__GenerateKeywordEmbeddings(keywords)
    for word, embed in keywordEmbeddings.items():
      print(f'\n\n\n\n word: {word}\n float: {embed}')

    print('\n')
    print('\n')
    print('\n')
    print('\n')
    print('\n')
    print('\n')

    # group the keywords by the cluster id
    labels = self.__IdentifyClusters(
      [embed for embed in keywordEmbeddings.values()]
    )
    clusterGroups: dict[int, list[str]] = {}
    for kw, cid in zip(keywords, labels):
      clusterGroups.setdefault(cid, []).append(kw)

    # get best name for each cluster
    clusterFieldNames: dict[int, str] = (
      self.__IdentifyBestKeywordForEachClusterGroup(
        clusterGroups, keywordEmbeddings
      )
    )

    # trim low value clusters
    clusterScores: list[tuple[int, float]] = []
    for cid, kws in clusterGroups.items():
      for word in kws:
        print(
          f'\n\n\n\nword: {word}, \nvalue: {keywordEmbeddings.get(word, 1.0)}'
        )
        print(type(keywordEmbeddings.get(word, 1.0)))
      # clusterScores.append((cid, score))

    # clusterScores.sort(key=lambda x: x[1], reverse=True)
    # keepClusterIds = [
    #   cid for cid, _ in clusterScores[: self.maxNumberOfKeywords]
    # ]

    # for cid in keepClusterIds:
    #   print(clusterFieldNames[cid])

    # calculate the statistics for the process.
    self.statisticsObject.EndTime = time.time() * 1000
    self.statisticsObject.ProcessingTime = (
      self.statisticsObject.EndTime - self.statisticsObject.StartTime
    )
    return '', True, self.statisticsObject

  def __IdentifyBestKeywordForEachClusterGroup(
    self,
    clusterGroups: dict[int, list[str]],
    keywordEmbeddings: dict[str, float],
  ):
    clusterFieldName: dict[int, str] = {}
    for cid, phrases in clusterGroups.items():
      bestPhrase = max(
        phrases, key=lambda p: (keywordEmbeddings.get(p, 1.0), -len(p))
      )
      clusterFieldName[cid] = self.clean_field_name(bestPhrase)
    return clusterFieldName

  def __IdentifyClusters(self, embeddings: list[float], k: int = 25):
    kmeans = KMeans(n_clusters=k, random_state=42)
    labels = kmeans.fit_predict(embeddings)
    return labels

  async def __GenerateKeywordEmbeddings(
    self, keywords: list[str], k: int = 25
  ) -> dict[str, float]:
    # ) -> list[tuple[str, Any]]:
    embeddings = await self.llm.GetEmbeddingsForContent(keywords)
    # Each vector is inside its own list.
    # pull all vectors up so they go from [[[1,1,1]], [[2,2,2]]] to [[1,1,1],[2,2,2]]
    embeddings = [embed[0] for embed in embeddings]
    # result: list[dict[str, float]] = []
    result = dict(zip(keywords, embeddings))
    return result

  def clean_field_name(self, phrase: str) -> str:
    """
    Convert a phrase into a safe Typesense field name.
    Example: "Creation Date" -> "creation_date"
    """
    name = phrase.strip().lower()
    # Replace spaces with underscores
    name = name.replace(' ', '_')
    # Remove characters you don't want (very simple version)
    allowed = 'abcdefghijklmnopqrstuvwxyz0123456789_'
    name = ''.join(ch for ch in name if ch in allowed)
    return name
