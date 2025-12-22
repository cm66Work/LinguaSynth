import ast
import json
import time
from typing import override
from APIs.ProcessingPipeline.DocumentIngestors.IDocumentIngestor import (
  IDocumentIngestor,
  StatisticObject,
)
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.ServerResponse import ServerResponseV2


class SimpleDocumentIngestion(IDocumentIngestor):
  @override
  def __init__(
    self,
    minio: MinIO_Object,
    typesense: Typesense_Object,
    serverResponse: ServerResponseV2,
  ) -> None:
    super().__init__(minio, typesense, serverResponse)

  async def IndexDocument(
    self, documentName: str, document: dict[str, str], collectionName: str
  ) -> tuple[str, bool, StatisticObject]:
    await super().IndexDocument(documentName, document, collectionName)

    result = self.typesense.IndexFileIntoCollection(
      json.dumps(ast.literal_eval(str(document))), collectionName
    )

    self.statisticsObject.ProcessingTime = (time.time() * 1000) - self.startTime
    return result.Message, result.Success, self.statisticsObject
