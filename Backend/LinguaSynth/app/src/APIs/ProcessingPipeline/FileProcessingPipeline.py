from dataclasses import dataclass, field
from APIs.ProcessingPipeline.DocumentProcessors.IDocumentProcessor import (
  DocumentResponseObject,
  IDocumentProcessor,
  StatisticsObject,
)

from APIs.ProcessingPipeline.DocumentProcessors import (
  KeywordExtractionDocumentProcessor,
  RAKEExtraction,
  YAKEExtraction,
  RawTextExtraction,
  TokenizationExtraction,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.ServerResponse import ServerResponseV2, ServerResponseObject


@dataclass
class FilePipelineResponseObject(ServerResponseObject):
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
    self.__InitProcessors()

  def __InitProcessors(self):
    self.AddProcessor(
      KeywordExtractionDocumentProcessor.KeywordExtractionDocumentProcessor(
        self.minio, self.serverResponse, 'keyword-extraction-raw-database'
      ),
      'key_word_extraction',
    )
    self.AddProcessor(
      RAKEExtraction.RAKEExtraction(
        self.minio, self.serverResponse, 'rake-extraction-raw-database'
      ),
      'rake_extraction',
    )
    self.AddProcessor(
      YAKEExtraction.YAKEExtraction(
        self.minio, self.serverResponse, 'yake-extraction-raw-database'
      ),
      'yake_extraction',
    )
    self.AddProcessor(
      TokenizationExtraction.TokenizationExtraction(
        self.minio, self.serverResponse, 'token-extraction-raw-database'
      ),
      'token_extraction',
    )
    self.AddProcessor(
      RawTextExtraction.RawTextExtraction(
        self.minio, self.serverResponse, 'raw-text-extraction-raw-database'
      ),
      'raw_extraction',
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
