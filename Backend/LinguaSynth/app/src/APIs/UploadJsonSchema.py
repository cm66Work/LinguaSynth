import json
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.LogUtils import ErrorTypes
from Utils.ServerResponse import ServerResponse


async def UploadJsonSchema(
  schemaName: str,
  schemaJsonString: str,
  serverResponse: ServerResponse,
  typesenseObject: Typesense_Object,
  force: bool = False,
):
  """
  Uploads the given schema as a new typesense collection schema.

  Args:
      schemaName: str : the schemas name.
      schemaJsonString: str : the json string for the schema.
      force : bool : if true then it will override any existing schemas with the same name.
  """
  currentResponse = serverResponse.GenerateServerResponse(
    success=True,
    message='',
    extraData={},
    finished=False,
  )

  currentResponse.Message = 'Processing...'
  yield vars(currentResponse)

  if len(schemaName) <= 0:
    yield vars(
      serverResponse.GenerateServerResponse(
        success=False,
        message='Schema name has not been provided',
        extraData={},
        errorType=ErrorTypes.Error,
        className='main',
        finished=True,
      )
    )
    return

  if not typesenseObject.SchemaExists(schemaName):
    yield vars(
      serverResponse.GenerateServerResponse(
        success=False,
        message='Schema already exists',
        extraData={},
        errorType=ErrorTypes.Info,
        className='main',
        finished=True,
      )
    )
    if not force:
      yield vars(
        serverResponse.GenerateServerResponse(
          success=False,
          message='Schema overriding is currently protected. Set force to True to disable.',
          extraData={},
          errorType=ErrorTypes.Info,
          className='main',
          finished=True,
        )
      )
      return
    else:
      yield vars(
        serverResponse.GenerateServerResponse(
          success=False,
          message='Forcing override of existing schema.',
          extraData={},
          errorType=ErrorTypes.Warning,
          className='main',
          finished=True,
        )
      )

  try:
    jsonSchema = json.loads(schemaJsonString)
    finalSchemaString = '{' + f"'name': '{schemaName}', 'fields': ["
    fields: list[str] = []
    for tag in jsonSchema:
      field = f"{{'name': '{tag['tag'].replace(' ', '_')}', 'type': "

      if tag['type'] == 'Number':
        field += "'init32'"
      else:
        field += "'string'"

      field += '}'
      fields.append(field)

    fields.append("{'name': 'document_id', 'type': 'int32'}")
    finalFields = ','.join(fields)
    finalSchemaString += f'{finalFields} ] ' + '}'

    yield vars(
      typesenseObject.ImportSchema(finalSchemaString.replace("'", '"'), force=force)
    )

  except Exception as e:
    print(e)
    print('failed')
    yield vars(
      serverResponse.GenerateServerResponse(
        success=False,
        message=f'{e}',
        extraData={},
        errorType=ErrorTypes.Error,
      )
    )
