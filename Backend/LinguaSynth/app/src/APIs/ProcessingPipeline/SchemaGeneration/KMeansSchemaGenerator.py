from dataclasses import asdict
import time
import json
import re
import math
from typing import Any, Optional, override
from APIs.ProcessingPipeline.DocumentProcessors import (
  KeywordExtractionDocumentProcessor,
)
from APIs.ProcessingPipeline.SchemaGeneration.ISchemaGenerator import (
  DATE_LIKE_TERMS,
  NUMERIC_LIKE_TERMS,
  ISchemaGenerator,
  SchemaTemplate,
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
    wordFrequency: float = 0.9,
    maxKeywords: int = 20,  # keep the top 20 best scoring groups for typesense fields.
  ):
    super().__init__(minio, uploadServerResponse, generatorName)
    # self.wordFrequency = wordFrequency
    self.llm = llm
    # self.maxNumberOfKeywords = maxKeywords

  async def GenerateSchema(
    self, keywords: list[str], targetBucketName: str
  ) -> tuple[str, bool, StatisticsObject]:
    await super().GenerateSchema(keywords, targetBucketName)
    startTime = time.time() * 1000

    # Keywords and then their embedded vector
    keywordEmbeddings: dict[
      str, float
    ] = await self.__GenerateKeywordEmbeddings(keywords)

    # group the keywords by the cluster id
    labels = self.__IdentifyClusters(
      embeddings=[embed for embed in keywordEmbeddings.values()], k=4
    )
    # The cluster groups are the new Schemas.
    # - A group cluster means that all vectors in that cluster share a similar meaning to one another.
    clusterGroups: dict[int, list[str]] = {}
    for kw, cid in zip(keywords, labels):
      clusterGroups.setdefault(cid, []).append(kw)
    newSchemas: list[SchemaTemplate] = []
    for clusterId in clusterGroups:
      # We dont want schemas that are two small, < 3 tags, so ignore them.
      if len(clusterGroups[clusterId]) < 3:
        continue
      # We could have way to many words in each cluster.
      # Current target for best speed and accuracy is between 10-20 keywords per cluster.
      # It is okay if we do not capture all the data in one go, since this process is mean to be ran
      # multiple times.
      if len(clusterGroups[clusterId]) >= 20:
        # Decimate the number of keywords in the cluster to a max of 20.
        # So we get an even spread of the vector points.
        decimateFactor: int = math.floor(len(clusterGroups[clusterId]) / 20)
        clusterGroups[clusterId] = clusterGroups[clusterId][
          :-decimateFactor:decimateFactor
        ]
      schemaName = self.RepresentativePhrase(
        clusterGroups[clusterId], keywordEmbeddings
      ).replace(' ', ' ')
      generatedSchema: SchemaTemplate = await self.__BuildTypesenseSchema(
        schemaName, clusterGroups[clusterId]
      )
      newSchemas.append(generatedSchema)

    # Upload the processed file to Minio
    for schema in newSchemas:
      jsonSchema = json.dumps(asdict(schema))
      # print(f'schema: {schema.name}')
      await self.fileUploader.UploadDocumentContentAsFile(
        jsonSchema, f'{targetBucketName}-{schema.name}.txt'
      )

    # calculate the statistics for the process.
    self.statisticsObject.ProcessingTime = (time.time() * 1000) - startTime
    self.statisticsObject.schemaTemplates = newSchemas
    # return uploadResult.Message, uploadResult.Success, self.statisticsObject
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
    """
    Identifies K number of clusters within the given embeddings.

    :param self: Description
    :param embeddings: Description
    :type embeddings: list[float]
    :param k: Description
    :type k: int
    """
    kmeans = KMeans(n_clusters=k, random_state=42)
    labels = kmeans.fit_predict(embeddings)
    return labels

  async def __GenerateKeywordEmbeddings(
    self, keywords: list[str], k: int = 25
  ) -> dict[str, float]:
    embeddings = await self.llm.GetEmbeddingsForContent(keywords)
    return dict(zip(keywords, embeddings))

  def clean_field_name(self, phrase: str) -> str:
    """
    Convert a phrase into a safe Typesense field name.
    Example: "Creation Date" -> "creation_date"
    """
    clean = [
      re.sub(r'\s+', ' ', re.sub(r'[()\[\]{}\"\.]', '', k)) for k in phrase
    ]
    name: str = str().join(clean)
    name = name.strip().lower().replace(' ', ' ')
    # Remove characters you don't want (very simple version)
    allowed = 'abcdefghijklmnopqrstuvwxyz0123456789_'
    name = ''.join(ch for ch in name if ch in allowed)
    return name

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

  async def __BuildTypesenseSchema(
    self,
    schemaName: str,
    keywords: list[str],
    maxFields: Optional[int] = None,
  ) -> SchemaTemplate:
    # Make sure the schema name is clean.
    # We dont need to clean the field since that is done before this is ran.
    clean = [
      re.sub(r'\s+', ' ', re.sub(r'[()\[\]{}\"\.]', '', k))
      for k in schemaName.split('_')
    ]
    schemaName = '_'.join(clean).lower()
    fields: list[dict[str, Any]] = []
    seenNames = set()

    processedWordCount: int = 0
    for i, keyword in enumerate(keywords):
      if maxFields is not None and len(fields) >= maxFields:
        break
      processedWordCount += 1
      print(f'Processing word: {processedWordCount} / {len(keywords)}')
      raw = keyword.strip()
      if not raw:
        continue
      fieldName = self.__ToFieldName(raw)

      if fieldName in seenNames:
        continue
      if fieldName == 'id':
        # Typesense already uses "id" as the document identifier
        continue

      summarizedFiledName: str = await self.GenerateSummaryWord(fieldName)
      fieldType = self.__InferFieldType(summarizedFiledName)

      fieldDef: dict[str, Any] = {
        'name': summarizedFiledName,
        'type': fieldType,
      }

      fields.append(fieldDef)
      # Add the original field name so we can compare against the remaining in the documents.
      # The summarized field name has been mutated and will no longer match.
      seenNames.add(fieldName)

    # defaultSortingField = None
    # for f in fields:
    #   if f['type'] in ('int32', 'float'):
    #     defaultSortingField = f['name']
    #     break

    schema: SchemaTemplate = SchemaTemplate(schemaName, fields)
    # schema: dict[str, Any] = {'name': collection_name[1:-1], 'fields': fields}

    # if defaultSortingField is not None:
    #   schema['default_sorting_field'] = defaultSortingField
    return schema

  # region schema name generation
  """
  Computes a semantic label for a collection of keyword embeddings by finding
  the densest region in embedding space.

  The process normalizes all vectors, calculates their centroid to represent
  the semantic center of the keyword set, and then selects the keyword or
  combined phrase whose embedding is closest to that center using cosine
  similarity.

  This is useful for generating a representative word or short phrase that
  best describes the overall meaning of a group of related keywords.
  """

  def Normalize(self, v):
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v] if norm else v

  def centroid(self, vectors: list) -> list[float]:
    dim = len(vectors[0])
    c = [0.0] * dim
    for v in vectors:
      for i in range(dim):
        c[i] += v[i]
    return [x / len(vectors) for x in c]

  def cosine_similarity(self, a, b) -> int:
    return sum(x * y for x, y in zip(a, b))

  async def RepresentativeKeyword(
    self, keywords: list[str], embeddings: dict[str, float]
  ) -> str:
    cleanKeywords: list[str] = []
    for word in keywords:
      if len(word) > 0:
        cleanKeywords.append(word)

    keys = list(embeddings.keys())
    vectors = [self.Normalize(embeddings[k]) for k in keys]

    center = self.centroid(vectors)

    best_key = ''
    best_score = float('-inf')

    for key, vec in zip(keys, vectors):
      score = self.cosine_similarity(vec, center)
      if score > best_score:
        best_score = score
        best_key = key

    return best_key

  def RepresentativePhrase(
    self, keywords: list[str], embeddings: dict[str, float], top_n: int = 3
  ) -> str:
    """
    Selects a compact phrase that best represents a group of keywords by
    measuring how close each keyword vector sits to the collective center.

    The method assumes all embeddings already exist and focuses only on the
    provided keywords, ignoring unrelated vectors entirely.

    The final phrase is formed by joining the most central keywords, ordered
    by relevance, into a single lowercase token.

    :param self: Description
    :param keywords: Description
    :type keywords: list[str]
    :param embeddings: Description
    :type embeddings: dict[str, float]
    :param top_n: Description
    :type top_n: int
    :return: Description
    :rtype: str
    """
    # we have been given all the embeddings.
    # But we only want to look at the words in our keyword list.
    # Reduce the embedding space to only terms we actually care about.
    # This avoids contaminating the centroid with unrelated vectors.
    keywordEmbeddings: dict[str, float] = {}
    for word in embeddings.keys():
      if word in keywords:
        keywordEmbeddings[word] = embeddings[word]

    # Normalize each vector so magnitude does not influence similarity.
    # Direction alone should define how representative a keyword is.
    vectors: list = [
      self.Normalize(keywordEmbeddings[k]) for k in keywordEmbeddings.keys()
    ]

    # Compute the geometric center of all keyword vectors.
    # This acts as a conceptual anchor for the topic.
    center = self.centroid(vectors)

    # Score each keyword by how closely it aligns with the center.
    # Higher cosine similarity implies stronger thematic alignment.
    scored = [
      (key, self.cosine_similarity(vec, center))
      for key, vec in zip(keywordEmbeddings.keys(), vectors)
    ]

    # Rank keywords from most representative to least.
    scored.sort(key=lambda x: x[1], reverse=True)

    # Merge the top candidates into a single phrase.
    # Underscores preserve token boundaries for downstream processing.
    return ' '.join(key for key, _ in scored[:top_n]).lower()

  async def GenerateSummaryWord(self, phrase: str) -> str:
    """
    Takes in an extracted key phrase that will be used for the schema and generates a summary word using an llm.

    :param self: Description
    :param phrase: Description
    :type phrase: str
    :return: Description
    :rtype: str
    """
    result = await self.llm.Generate(
      f'Summaries the following word or sentence into a single high search keyword for use in a search engine. Phrase: {phrase} \n Only respond with the result and nothing else. Do not use unicode characters.'
    )
    if len(result.Response) > 25 or len(result.Response) == 0:
      return phrase.replace(' ', ' ')
    else:
      return result.Response.lower().replace(' ', ' ').replace('\n', '')


# endregion
