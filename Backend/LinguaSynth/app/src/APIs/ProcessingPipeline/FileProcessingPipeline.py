from dataclasses import dataclass, field
from APIs.ProcessingPipeline.DocumentProcessors.IDocumentProcessor import (
  DocumentResponseObject,
  IDocumentProcessor,
  StatisticsObject,
)
from APIs.ProcessingPipeline.DocumentProcessors.KeywordExtractionDocumentProcessor import (
  KeywordExtractionDocumentProcessor,
)
from APIs.ProcessingPipeline.DocumentProcessors.RAKEExtraction import (
  RAKEExtraction,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2
from Utils.ServerResponse import ServerResponseObject


@dataclass
class PipelineResponseObject(ServerResponseObject):
  TotalTimeToComplete: float = 0
  AverageTimeToProcessEachDocument: float = 0.0
  TotalDocumentsProcessed: int = 0
  NumberOfDocumentsProcessed: int = 0
  ProcessResponseObjects: list[DocumentResponseObject] = field(
    default_factory=list[DocumentResponseObject]
  )


class FileProcessingPipelines:
  def __init__(
    self, minio: MinIO_Object, serverResponse: ServerResponseV2
  ) -> None:
    self.documentProcessors: list[IDocumentProcessor] = []
    self.minio = minio
    self.pipelineResponseObject: list[DocumentResponseObject] = []
    self.serverResponse = serverResponse
    self.__initProcessors()

  def __initProcessors(self):
    self.AddProcessor(
      KeywordExtractionDocumentProcessor(
        self.minio, self.serverResponse, 'keyword-extraction-raw-database'
      ),
      'key_word_extraction',
    )
    self.AddProcessor(
      RAKEExtraction(
        self.minio, self.serverResponse, 'rake-extraction-raw-database'
      ),
      'rake_extraction',
    )

  def AddProcessor(self, processor: IDocumentProcessor, processName: str):
    self.documentProcessors.append(processor)
    # grabbing the newly added processors response object so we can collect data on it.
    self.pipelineResponseObject.append(
      DocumentResponseObject(ProcessName=processName)
    )

  async def Run(
    self, content: str, fileName: str
  ) -> tuple[list[DocumentResponseObject], bool]:
    for i in range(0, len(self.documentProcessors)):
      response = await self.documentProcessors[i].ProcessDocument(
        content, fileName
      )
      # add this processes statistics to the list for data logging.
      self.pipelineResponseObject[i].Statistics.append(
        response[2]
        if response[1]
        else StatisticsObject(fileName, -1, -1, -1, -1, -1)
      )
    return self.pipelineResponseObject, True
