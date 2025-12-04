from typing import Any, AsyncGenerator, Generator
from APIs.ProcessingPipeline.FileProcessingPipeline import (
  FileProcessingPipelines,
  PipelineResponseObject,
)
from APIs.UploadProcessedDocuments import UploadProcessedDocuments
from ObjectInterfaces.MinIO_Object import MinIO_Object
from Utils.LogUtils import ErrorTypes
from Utils.ServerResponse import ServerResponseObject, ServerResponseV2
from APIs.UploadNewDocument import Uploader


class DocumentProcessor:
  def __init__(
    self, minio: MinIO_Object, serverResponse: ServerResponseV2
  ) -> None:
    self.minio = minio
    self.serverResponse = serverResponse

  # region Document summarization and processing
  # Process all original documents to summarized formats.
  # is later used to indexing into Typesense.
  async def ProcessDocumentsInBucket(
    self,
    bucketName: str,
    postgresObject,
  ) -> AsyncGenerator[ServerResponseObject, Any]:
    currentResponse = PipelineResponseObject()
    currentResponse.Message = 'Processing....'

    fileProcessingPipeline: FileProcessingPipelines = FileProcessingPipelines(
      self.minio, self.serverResponse
    )
    # start processing all documents in this bucket using our different processing pipelines.
    if not await self.minio.BucketExists(bucketName):
      currentResponse.Message = f'No bucket with name: {bucketName} found.'
      currentResponse.Finished = True
      yield self.serverResponse.GenerateServerResponse(
        currentResponse,
        className=__name__,
        errorType=ErrorTypes.Error,
      )
      return

    # All the documents which where successfully processed so we can remove them after all processors are done with them.
    processedDocuments: list[str] = []
    # send off the number of documents in the bucket.
    currentResponse.NumberOfDocumentsProcessed = (
      self.minio.GetNumberOfObjectsInBucket(bucketName)
    )
    yield self.serverResponse.GenerateServerResponse(currentResponse)

    fileUploader: Uploader = Uploader(
      self.minio, self.serverResponse, 'processed-database'
    )
    for document in self.minio.GetObjectsInBucket(bucketName):
      currentResponse.TotalDocumentsProcessed += 1
      if document.object_name is None:
        continue
      content = self.minio.GetContentOfBucketObject(
        bucketName, document.object_name
      ).Data['content']
      result = await fileProcessingPipeline.Run(content, document.object_name)
      # print('\n', result[0])
      if result[1]:
        # print(
        #   await fileUploader.UploadDocumentContentAsFile(
        #     content, document.object_name
        #   )
        # )
        currentResponse.ProcessResponseObjects = result[0]
        processedDocuments.append(document.object_name)
      yield self.serverResponse.GenerateServerResponse(currentResponse)

    # Remove the processed documents from the bucket so we know that we dont have to process them again later.
    for documentName in processedDocuments:
      self.minio.DeleteDocument(documentName, bucketName)
    currentResponse.Success = True
    currentResponse.Finished = True
    currentResponse.Message = 'Finished'
    yield self.serverResponse.GenerateServerResponse(currentResponse)
    return
