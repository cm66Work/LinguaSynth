import time
from typing import override
from APIs.ProcessingPipeline.QuestionAnswering.IQuestionAnswering import (
  IQuestionAnswering,
  DocumentReference,
  RunnerResponseObject,
)
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from typesense.types.collection import CollectionSchema
import json


class DefaultQuestionAnswering(IQuestionAnswering):
  @override
  def __init__(
    self, minio: MinIO_Object, llm: LLM_Object, typesense: Typesense_Object
  ) -> None:
    super().__init__(minio, llm, typesense)

  async def Run(
    self, userQuestion: str, collection: CollectionSchema
  ) -> tuple[bool, RunnerResponseObject]:
    await super().Run(userQuestion, collection)

    userQuery: dict[
      str, str
    ] = await self.__ConvertUserQuestionToTypesenseQuery(
      userQuestion, collection
    )

    # now search typesense for the documents.
    typesenseSearchResponse = self.typesense.AskQuestion(
      collection['name'], json.dumps(userQuery)
    )
    for document in typesenseSearchResponse.Data['documents']:
      self.responseObject.References.append(document['document']['id'])

    self.responseObject.ProcessingTime = (time.time() * 1000) - self.startTime
    return True, self.responseObject

  async def __ConvertUserQuestionToTypesenseQuery(
    self, userQuestion: str, collection: CollectionSchema
  ) -> dict[str, str]:
    queryBy: str = ''

    # TODO:: Add in query by selection

    # queryBy = collection['fields'][0]['name']  # type: ignore
    return {'q': userQuestion, 'query_by': '*'}
