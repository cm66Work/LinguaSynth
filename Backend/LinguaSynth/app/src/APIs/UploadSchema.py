from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils.LogUtils import ErrorTypes
from Utils.ServerResponse import ServerResponse, ServerResponseObject


async def UploadSchema(
  schemaName: str,
  newSchema: str,
  serverResponse: ServerResponse,
  typesenseObject: Typesense_Object,
  force: bool = False,
):
  """
  Uploads the given schema as a new typesense collection schema.

  Args:
      schemaName: str : the schemas name.
      schemaString: str : the field string for the schema.
      force : bool : if true then it will override any existing schemas with the same name.
  """

  currentResponse = ServerResponseObject()
  currentResponse.Message = 'Processing...'
  yield serverResponse.GenerateServerResponse(currentResponse)

  # run validation checks
  currentResponse = __Validation(
    schemaName, serverResponse, typesenseObject, force
  )
  if currentResponse.Finished:
    # Validation failed.
    yield currentResponse
    return
  yield currentResponse

  try:
    currentResponse = typesenseObject.ImportSchema(schemaName, newSchema, force)
    yield currentResponse

  except Exception as e:
    currentResponse.Success = False
    currentResponse.Message = f'{e}'
    currentResponse.Finished = True
    yield serverResponse.GenerateServerResponse(
      currentResponse,
      errorType=ErrorTypes.Error,
    )


def __Validation(
  schemaName: str,
  serverResponse: ServerResponse,
  typesenseObject: Typesense_Object,
  force: bool = False,
):
  validationResponse = serverResponse.GenerateServerResponse(
    ServerResponseObject(),
    className='Upload Schema',
  )
  if len(schemaName) <= 0:
    validationResponse.Message = (
      'Entered schema name is empty. Canceling upload of new schema.'
    )
    validationResponse.Success = False
    validationResponse.Finished = True
    return validationResponse

  if typesenseObject.SchemaExists(schemaName) and not force:
    validationResponse.Success = False
    validationResponse.Finished = True
    validationResponse.Message = 'Schema already exists. Schema overriding is currently protected. Set force to True to disable override protection.'
    return validationResponse
  elif typesenseObject.SchemaExists(schemaName) and force:
    validationResponse.Success = True
    validationResponse.Finished = False
    validationResponse.Message = 'Forcing override of existing schema.'
    return validationResponse

  validationResponse.Message = 'New Schema detected.'
  return validationResponse
