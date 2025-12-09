import json
import time
from typing import override

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
    wordFrequency: float = 0.3,
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
    selectedKeywords: list[str] = self.SelectCandidateFields(keywords)
    self.statisticsObject.selectedKeywords = selectedKeywords
    self.statisticsObject.selectedKeywordsCount = len(selectedKeywords)

    schemaName: str = self.GenerateSchemaName(selectedKeywords)
    self.statisticsObject.newSchemaName = schemaName

    generatedSchema: dict = self.GenerateFinalSchema(
      selectedKeywords, schemaName
    )

    # Upload the processed file to Minio
    schemaAsJson = json.dumps(generatedSchema)
    uploadResult = await self.fileUploader.UploadDocumentContentAsFile(
      schemaAsJson,
      f'{targetBucketName}-{schemaName}.txt',
    )

    return uploadResult.Message, uploadResult.Success, self.statisticsObject

  def SelectCandidateFields(self, keywords: list[str]) -> list[str]:
    selectedKeywords: list[str] = []
    # TODO:: select the highest frequency key words.
    return keywords[0:5]  # Inclusive - exclusive

  def GenerateSchemaName(self, keywords: list[str]) -> str:
    name = (
      str(keywords[0:3])
      .lower()
      .replace(' ', '-')
      .replace(',', '')
      .replace("'", '')
    )
    return name

  def GenerateFinalSchema(self, keywords: list[str], schemaName: str) -> dict:
    # TODO:: Generate the schema
    return {}
