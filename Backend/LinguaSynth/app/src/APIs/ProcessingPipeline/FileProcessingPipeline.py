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
  DocumentsProcessed: int = 0
  TotalDocuments: int = 0
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
    # self.AddProcessor(
    #   KeywordExtractionDocumentProcessor.KeywordExtractionDocumentProcessor(
    #     self.minio, self.serverResponse, 'keyword-normalization'
    #   ),
    #   'key_word_normalization',
    # )
    # self.AddProcessor(
    #   RAKEExtraction.RAKEExtraction(
    #     self.minio, self.serverResponse, 'rake-normalization'
    #   ),
    #   'rake_normalization',
    # )
    # self.AddProcessor(
    #   YAKEExtraction.YAKEExtraction(
    #     self.minio, self.serverResponse, 'yake-normalization'
    #   ),
    #   'yake_normalization',
    # )
    # self.AddProcessor(
    #   TokenizationExtraction.TokenizationExtraction(
    #     self.minio, self.serverResponse, 'token-normalization'
    #   ),
    #   'token_extraction',
    # )
    self.AddProcessor(
      RawTextExtraction.RawTextExtraction(
        self.minio, self.serverResponse, 'raw-no-normalization'
      ),
      'raw_no_normalization',
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
      # print(f'{fileName}: Processing...')
      response = await self.documentProcessors[i].ProcessDocument(
        content, fileName
      )
      # add this processes statistics to the list for data logging.
      self.pipelineResponseObject[i].Statistics.append(
        response[2] if response[1] else StatisticsObject(fileName, -1, -1, -1)
      )
      # print(f'{fileName}: Done')
    return self.pipelineResponseObject, True
