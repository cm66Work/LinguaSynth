from Utils.LogUtils import ErrorTypes, LogUtil
from dataclasses import dataclass, field


@dataclass
class ServerResponseObject:
  """Data class for the server response"""

  # Using to stop prevent strongly typed variables / keys
  Success: bool = False
  Message: str = ''
  Data: dict = field(default_factory=dict)
  Finished: bool = False


class ServerResponse(LogUtil):
  def __init__(self, rootFolder: str, logBaseName: str):
    super().__init__(rootFolder, logBaseName)

  def GenerateServerResponse(
    self,
    serverResponseObject: ServerResponseObject,
    className: str = '',
    errorType: ErrorTypes = ErrorTypes.Ok,
    generateLog=True,
  ):
    """
    Private helper function to keep return message code DRY.
    Handles generating log messages for the action.

    Args:
      success (bool): if the action was successful.
      message (str): the message to log and return
      extraData (dict): any extra information that should be returned
    Return:
      Object with both a result (bool) and message (str).
      Also returns extraData on the end if any passed.
    """
    if generateLog or len(serverResponseObject.Message) > 0:
      self.GenerateLogMessage(
        serverResponseObject.Message, className=className, errorType=errorType
      )
    return ServerResponseObject(
      Success=serverResponseObject.Success,
      Message=serverResponseObject.Message,
      Data=serverResponseObject.Data,
      Finished=serverResponseObject.Finished,
    )
