from dataclasses import dataclass
import json
from typing import cast, List, Dict, Any
from unittest import result
import numpy as np
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from ObjectInterfaces.LLM_Object import (
  EmbeddingVectorDocumentGenerator,
  LLM_Object,
)
from typesense.types.document import DocumentSchema
from typesense.types.collection import CollectionSchema
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils.QuoteMatcher import QuoteObject, SchemaMatcher
from Utils.SemanticFieldMatcher import SemanticFieldMatcher


async def Iterate(typesenseObject: Typesense_Object, minioObject: MinIO_Object):
  return await CalculateAccuracy(typesenseObject, minioObject)


async def CalculateAccuracy(
  typesenseObject: Typesense_Object, minioObject: MinIO_Object
):
  getAllDocument = {'q': '*', 'query_by': '*'}

  schemas = typesenseObject.GetAllSchemas()

  for schema in schemas:
    response = typesenseObject.AskQuestion(
      schema['name'], json.dumps(getAllDocument)
    )
    documents = response.Data['documents']
    for document in documents:
      print(document['document']['document_name'])
