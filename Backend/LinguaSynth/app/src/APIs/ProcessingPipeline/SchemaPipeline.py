from dataclasses import dataclass, field
from APIs.ProcessingPipeline.SchemaGeneration.FrequencySchemaGenerator import (
  FrequencyDrivenSchemaGenerator,
)
from APIs.ProcessingPipeline.SchemaGeneration.ISchemaGenerator import (
  GeneratorResponseObject,
  ISchemaGenerator,
  StatisticsObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2, ServerResponseObject


@dataclass
class SchemaPipelineResponseObject(ServerResponseObject):
  TotalTimeToComplete: float = 0
  AverageTimeToProcessEachDocument: float = 0.0
  TotalDocumentsProcessed: int = 0
  NumberOfDocumentsProcessed: int = 0
  ProcessResponseObjects: list[GeneratorResponseObject] = field(
    default_factory=list[GeneratorResponseObject]
  )


class SchemaPipeline:
  def __init__(
    self, minio: MinIO_Object, serverResponse: ServerResponseV2
  ) -> None:
    self.schemaGenerators: list[ISchemaGenerator] = []
    self.minio = minio
    self.pipelineResponseObjects: list[GeneratorResponseObject] = []
    self.serverResponse = serverResponse
    self.__InitGenerators()

  def __InitGenerators(self) -> None:
    self.AddGenerator(
      FrequencyDrivenSchemaGenerator(
        self.minio, self.serverResponse, 'frequency'
      ),
      'frequency_driven_schema_generation',
    )

  def AddGenerator(self, generator: ISchemaGenerator, processName: str) -> None:
    self.schemaGenerators.append(generator)
    self.pipelineResponseObjects.append(
      GeneratorResponseObject(ProcessName=processName)
    )

  async def Run(
    self, keywords: list[str], targetBucketName: str
  ) -> tuple[list[GeneratorResponseObject], bool]:
    for i in range(0, len(self.schemaGenerators)):
      response = await self.schemaGenerators[i].GenerateSchema(
        keywords, targetBucketName
      )
      self.pipelineResponseObjects[i].Statistics.append(
        response[2]
        if response[1]
        else StatisticsObject('error', 'error', [], 0, -1, -1, -1)
      )

    return self.pipelineResponseObjects, True
