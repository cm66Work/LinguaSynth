# get all the test documents from the test collection
# convert them into a list of type Question
## Question contains the question message, correct answer, given answer, accuracy.
import csv
from dataclasses import asdict, dataclass, field
import io
import json
import time
from typing import Any, AsyncGenerator, cast

from APIs.ProcessingPipeline.QuestionAnswering.IQuestionAnswering import (
  DocumentReference,
)
from APIs.ProcessingPipeline.QuestionAnsweringPipeline import (
  QuestionAnsweringPipeline,
)
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.ServerResponse import ServerResponseObject, ServerResponseV2
from typesense.types.collection import CollectionSchema
from APIs.ProcessingPipeline.QuestionAnsweringPipeline import (
  PipelineResponseObject,
)


@dataclass
class Question:
  Id: int
  Q: str
  CorrectDocumentId: list[int]
  DocumentGivenId: list[int]
  AnswerIsCorrect: bool
  Confidence: float
  TimeToAnswer: float


@dataclass
class TestResponse(ServerResponseObject):
  CorrectQuestions: int = 0
  IncorrectQuestions: int = 0
  CanNotAnswer: int = 0
  AverageConfidence: float = 0.0
  TotalTimeToComplete: float = 0
  Questions: list[Question] = field(default_factory=list[Question])


class TestRunner:
  def __init__(
    self,
    typesense: Typesense_Object,
    minio: MinIO_Object,
    llm: LLM_Object,
    serverResponse: ServerResponseV2,
  ) -> None:
    self.minio = minio
    self.typesense = typesense
    self.serverResponse = serverResponse
    self.llm = llm
    self.questionPipeline = QuestionAnsweringPipeline(
      minio, typesense, llm, serverResponse
    )
    self.currentResponse = TestResponse()

  async def RunTests(
    self,
    inputBucket: str,
    answerBucket: str,
    collectionSchemas: list[CollectionSchema],
    outputBucket: str,
  ) -> AsyncGenerator[ServerResponseObject, Any]:
    startTime: float = time.time() * 1000
    self.currentResponse.Message = 'Running tests....'
    yield self.serverResponse.GenerateServerResponse(self.currentResponse)

    self.currentResponse.Message = 'Loading Questions....'
    yield self.serverResponse.GenerateServerResponse(self.currentResponse)
    questions: list[Question] = await self.LoadTestsQuestions(inputBucket)
    questions = await self.LoadTestQuestionAnswers(answerBucket, questions)
    self.currentResponse.Message = 'Questions Loaded Running Tests...'
    yield self.serverResponse.GenerateServerResponse(self.currentResponse)
    questions = await self.TestSystem(questions, collectionSchemas)

    questions = self.CheckAnswers(questions)

    self.currentResponse.Questions = questions

    self.currentResponse.Message = 'Finished'
    self.currentResponse.Success = True
    self.currentResponse.Finished = True
    self.currentResponse.TotalTimeToComplete = (time.time() * 1000) - startTime
    yield self.serverResponse.GenerateServerResponse(self.currentResponse)

    # Upload results in the event our browser crashes.
    currentJsonResponse = json.dumps(asdict(self.currentResponse), indent=1)
    currentJsonResponse = json.loads(currentJsonResponse)
    # We have to flatten the output.
    data = currentJsonResponse
    flatData = [
      {
        # Top-level SchemaPipelineResponseObject
        'Correct Questions': data.get('CorrectQuestions'),
        'Incorrect Questions': data.get('IncorrectQuestions'),
        'Can Not Answer': data.get('CanNotAnswer'),
        'Total Time To Complete': data.get('TotalTimeToComplete'),
        'Average Confidence': data.get('AverageConfidence'),
      }
    ]

    memOutput = io.StringIO()
    writer = csv.DictWriter(memOutput, fieldnames=flatData[0].keys())  # noqa: F821
    writer.writeheader()
    writer.writerows(flatData)

    csvString = memOutput.getvalue()
    memOutput.close()
    self.minio.UploadDocumentToStorageServer(
      'n-question-generation-results',
      csvString,
      'n-question-generation.csv',
    )

  def CheckAnswers(self, questions: list[Question]) -> list[Question]:
    self.currentResponse.AverageConfidence = 0
    self.currentResponse.CanNotAnswer = 0
    self.currentResponse.CorrectQuestions = 0
    self.currentResponse.IncorrectQuestions = 0
    for i in range(len(questions)):
      if len(questions[i].CorrectDocumentId) <= 0:
        self.currentResponse.CanNotAnswer += 1
        continue
      correct = 0
      incorrect = 0
      # for returnedReference in questions[i].DocumentGivenId:
      #   if returnedReference in questions[i].CorrectDocumentId:
      #     correct += 1
      for returnedReference in questions[i].DocumentGivenId:
        if returnedReference in questions[i].CorrectDocumentId:
          correct += 1
        else:
          incorrect += 1

      accuracy = 0
      if len(questions[i].DocumentGivenId) > 0:
        accuracy = (correct / len(questions[i].DocumentGivenId)) * 100
      if accuracy > 0.45:
        self.currentResponse.CorrectQuestions += 1
      else:
        self.currentResponse.IncorrectQuestions += 1

      self.currentResponse.AverageConfidence += accuracy

      # questions[i].Confidence = correct / len(questions[i].CorrectDocumentId)

      # self.currentResponse.AverageConfidence += questions[i].Confidence
      # if questions[i].Confidence > 0.5:
      #   self.currentResponse.CorrectQuestions += 1
      # else:
      #   self.currentResponse.IncorrectQuestions += 1

    self.currentResponse.AverageConfidence = (
      self.currentResponse.AverageConfidence / len(questions)
    )
    return questions

  async def TestSystem(
    self, questions: list[Question], collectionSchemas: list[CollectionSchema]
  ) -> list[Question]:
    for question in questions:
      if len(question.CorrectDocumentId) <= 0:
        continue
      async for result in self.questionPipeline.Run(
        question.Q, collectionSchemas
      ):
        if not result.Finished:
          continue
        result = cast(PipelineResponseObject, result)
        for response in result.ResponseObjects:
          question.TimeToAnswer = response.ProcessingTime
          references: list[DocumentReference] = response.References
          for ref in references:
            try:
              # Need to check why this is getting confused
              docRef = ref.DocumentName.split('--')[1].split('.txt')[0]
              docRef = int(docRef)
            except Exception:
              docRef = -1
            question.DocumentGivenId.append(docRef)
      # break
    return questions

  # region Loading the test data
  async def LoadTestQuestionAnswers(
    self, answersBucket: str, questions: list[Question]
  ) -> list[Question]:
    for document in self.minio.GetObjectsInBucket(answersBucket):
      if document.object_name is None:
        continue
      content: str = self.minio.GetContentOfBucketObject(
        answersBucket, document.object_name
      ).Data['content']
      for line in content.splitlines():
        qId, docId, _, _ = line.split()
        qId = int(qId)
        docId = int(docId)
        for question in questions:
          if question.Id == qId:
            question.CorrectDocumentId.append(docId)
    return questions

  async def LoadTestsQuestions(self, inputBucket: str) -> list[Question]:
    testQuestions = []
    for document in self.minio.GetObjectsInBucket(inputBucket):
      if document.object_name is None:
        continue

      content: str = self.minio.GetContentOfBucketObject(
        inputBucket, document.object_name
      ).Data['content']

      questionMerged = ' '.join([line for line in content.splitlines()])
      questionStrings: list[str] = questionMerged.split('.I ')
      for i in range(len(questionStrings)):
        if i == 0:
          continue
        questionSplit = questionStrings[i].split('.W ')
        # print(len(questionSplit))
        questionStrings[i] = (
          questionSplit[0].strip()
          if len(questionSplit) == 1
          else questionSplit[1].strip()
        )
        questionSplit = questionStrings[i].split('.B')
        questionStrings[i] = (
          questionStrings[i]
          if len(questionSplit) == 1
          else questionSplit[0].strip()
        )

        testQuestions.append(
          Question(i, questionStrings[i], [], [], False, 0, 0)
        )
    return testQuestions


# endregion
