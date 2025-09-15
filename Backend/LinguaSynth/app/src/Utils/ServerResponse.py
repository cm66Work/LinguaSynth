from Utils.LogUtils import LogUtil
from dataclasses import dataclass


@dataclass
class ServerResponseObject:
  """Data class for the server response"""

  # Using to stop prevent strongly typed variables / keys
  Success: bool
  Message: str
  Data: dict


class ServerResponse(LogUtil):
  def __init__(self, rootFolder: str, logBaseName: str):
    super().__init__(rootFolder, logBaseName)

  def GenerateServerResponse(
    self, success: bool, message: str, extraData: dict = {}, generateLog=True
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
    if generateLog:
      self.GenerateLogMessage(message)
    return ServerResponseObject(Success=success, Message=message, Data=extraData)
