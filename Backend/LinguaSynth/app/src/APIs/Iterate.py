import json
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object


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
