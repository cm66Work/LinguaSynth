import time
import re
from typing import Any, Optional
from dataclasses import dataclass, field
from ObjectInterfaces.MinIO_Object import MinIO_Object
from APIs.UploadNewDocument import Uploader
from Utils.ServerResponse import ServerResponseV2, ServerResponseObject

NUMERIC_LIKE_TERMS = [
  # identifiers
  'id',
  'code',
  'number',
  'num',
  'index',
  'ref',
  'reference',
  'key',
  # counts / sizes
  'count',
  'total',
  'amount',
  'quantity',
  'qty',
  'size',
  'length',
  'width',
  'height',
  'depth',
  'volume',
  'capacity',
  # financial
  'price',
  'cost',
  'value',
  'amount',
  'balance',
  'rate',
  'fee',
  'tax',
  'salary',
  'wage',
  # versioning / ordering
  'version',
  'revision',
  'rev',
  'level',
  'rank',
  # metrics
  'score',
  'rating',
  'points',
  'weight',
  'mass',
  'speed',
  # time-like but numeric (not dates)
  'duration',
  'interval',
  'period',
  'year',
  'years',
  'age',
  # other useful technical numeric fields
  'limit',
  'range',
  'threshold',
  'index',
  'step',
  'iteration',
]
DATE_LIKE_TERMS = [
  'date',
  'day',
  'month',
  'year',
  'datetime',
  'timestamp',
  'time',
  'created',
  'creation',
  'created_on',
  'modified',
  'updated',
  'update',
  'published',
  'posted',
  'start',
  'start_date',
  'end',
  'end_date',
  'begin',
  'begin_date',
  'expiry',
  'expires',
  'expiration',
  'deadline',
  'due',
  'issued',
  'issue_date',
  'effective',
  'effective_date',
  'released',
  'release_date',
]


@dataclass
class SchemaTemplate:
  name: str
  fields: list[dict[str, Any]]


@dataclass
class StatisticsObject:
  targetSchemaName: str
  schemaTemplates: list[SchemaTemplate]
  ProcessingTime: float


@dataclass
class GeneratorResponseObject(ServerResponseObject):
  ProcessName: str = 'placeholder'
  TotalDocumentsProcessed: int = 0
  CurrentDocumentsProcessed: int = 0
  Statistics: list[StatisticsObject] = field(
    default_factory=list[StatisticsObject]
  )


class ISchemaGenerator:
  PREFIX_SCHEMA_BUCKET_NAME: str = 'schemas'

  def __init__(
    self,
    minio: MinIO_Object,
    uploadServerResponse: ServerResponseV2,
    generatorName: str,
  ):
    self.minio = minio
    self.generatorName = generatorName
    self.fileUploader = Uploader(
      minio,
      uploadServerResponse,
      f'{self.PREFIX_SCHEMA_BUCKET_NAME}-{self.generatorName}',
    )

  async def GenerateSchema(
    self, keywords: list[str], targetBucketName: str
  ) -> tuple[str, bool, StatisticsObject]:
    self.statisticsObject: StatisticsObject = StatisticsObject(
      'placeholder-name', [], -1
    )
    return (
      'placeholder',
      False,
      StatisticsObject('error', [], -1),
    )

  def __ToFieldName(self, keyword: str) -> str:
    name = keyword.strip().lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = name.strip('_')
    if not name:
      name = 'field'
    return name

  def __InferFieldType(self, keyword: str) -> str:
    k = keyword.lower()
    tokens = re.split(r'[^a-z0-9]+', k)
    if any(tok in NUMERIC_LIKE_TERMS for tok in tokens):
      return 'int32'
    if any(tok in DATE_LIKE_TERMS for tok in tokens):
      return 'init32'
    return 'string'

  def __BuildTypesenseSchema(
    self,
    collection_name: str,
    keywords: list[str],
    maxFields: Optional[int] = None,
  ) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    seenNames = set()

    for i, keyword in enumerate(keywords):
      if maxFields is not None and len(fields) >= maxFields:
        break
      raw = keyword.strip()
      if not raw:
        continue
      fieldName = self.__ToFieldName(raw)

      if fieldName in seenNames:
        continue
      if fieldName == 'id':
        # Typesense already uses "id" as the document identifier
        continue

      fieldType = self.__InferFieldType(raw)

      fieldDef: dict[str, Any] = {'name': fieldName, 'type': fieldType}

      fields.append(fieldDef)
      seenNames.add(fieldName)

    defaultSortingField = None
    for f in fields:
      if f['type'] in ('int32', 'float'):
        defaultSortingField = f['name']
        break

    schema: dict[str, Any] = {'name': collection_name[1:-1], 'fields': fields}

    if defaultSortingField is not None:
      schema['default_sorting_field'] = defaultSortingField
    return schema
