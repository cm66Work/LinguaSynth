import time
from dataclasses import dataclass, field
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from typesense.types.collection import CollectionSchema


@dataclass
class DocumentReference:
  DocumentName: str
  Confidence: float = 0


@dataclass
class RunnerResponseObject:
  RunnerName: str
  References: list[DocumentReference] = field(
    default_factory=list[DocumentReference]
  )
  GeneratedAnswer: str = ''
  ProcessingTime: float = 0


class IQuestionAnswering:
  def __init__(
    self,
    minio: MinIO_Object,
    llm: LLM_Object,
    typesense: Typesense_Object,
  ) -> None:
    self.minio = minio
    self.llm = llm
    self.typesense = typesense
    self.startTime = 0

  async def Run(
    self, userQuestion: str, collection: CollectionSchema
  ) -> tuple[bool, RunnerResponseObject]:
    self.responseObject = RunnerResponseObject('placeholder-name', [], '', -1)
    self.startTime = time.time() * 1000

    return False, self.responseObject

  async def __ConvertUserQuestionToTypesenseQuery(
    self, userQuestion: str, collection: CollectionSchema
  ) -> dict[str, str]:
    return {}
