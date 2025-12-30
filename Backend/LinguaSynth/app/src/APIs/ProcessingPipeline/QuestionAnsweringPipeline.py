from dataclasses import dataclass, field
from typing import Any, AsyncGenerator
from APIs.ProcessingPipeline.QuestionAnswering.DefaultQuestionAnswering import (
  DefaultQuestionAnswering,
)
from APIs.ProcessingPipeline.QuestionAnswering.IQuestionAnswering import (
  RunnerResponseObject,
  IQuestionAnswering,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from typesense.types.collection import CollectionSchema
from Utils.ServerResponse import ServerResponseV2, ServerResponseObject


@dataclass
class PipelineResponseObject(ServerResponseObject):
  CollectionName: str = ''
  ResponseObjects: list[RunnerResponseObject] = field(
    default_factory=list[RunnerResponseObject]
  )


class QuestionAnsweringPipeline:
  def __init__(
    self,
    minio: MinIO_Object,
    typesense: Typesense_Object,
    llm: LLM_Object,
    serverResponse: ServerResponseV2,
  ) -> None:
    self.minio = minio
    self.typesense = typesense
    self.llm = llm
    self.serverResponse: ServerResponseV2 = serverResponse
    self.pipelineResponseObjects: list[RunnerResponseObject] = []
    self.runners: list[IQuestionAnswering] = []
    self.__InitRunners()

  def __InitRunners(self):
    self.__AddRunner(
      DefaultQuestionAnswering(self.minio, self.llm, self.typesense),
      'default-question-answering',
    )

  def __AddRunner(self, runner: IQuestionAnswering, runnerName: str):
    self.runners.append(runner)
    self.pipelineResponseObjects.append(RunnerResponseObject(runnerName))

  async def Run(
    self, userQuestion: str, collectionSchemas: list[CollectionSchema]
  ) -> AsyncGenerator[ServerResponseObject, Any]:
    currentResponse: PipelineResponseObject = PipelineResponseObject()
    currentResponse.Message = 'Processing...'
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    schema: CollectionSchema = (
      await self.GetClosestMatchingCollectionNameToUserQuestion(
        userQuestion, collectionSchemas
      )
    )
    currentResponse.CollectionName = schema['name']
    currentResponse.Message = 'Best matching schema identified.'
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    currentResponse.Message = 'Searching....'
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    for i in range(0, len(self.runners)):
      response = await self.runners[i].Run(userQuestion, schema)
      self.pipelineResponseObjects[i] = (
        response[1]
        if response[0]
        else RunnerResponseObject('error', [], 'Failed to answer question', -1)
      )

    currentResponse.Message = 'Finished!'
    currentResponse.Finished = True
    currentResponse.Success = True
    currentResponse.ResponseObjects = self.pipelineResponseObjects
    yield self.serverResponse.GenerateServerResponse(currentResponse)

  async def GetClosestMatchingCollectionNameToUserQuestion(
    self, userQuestion: str, collectionSchemas: list[CollectionSchema]
  ) -> CollectionSchema:
    # We can later expand this into its own pipeline if we need to tets different ways to selected which collection best matches the user questions.

    return self.typesense.GetAllSchemas()[
      0
    ]  # TODO:: Change to select the most related schema
