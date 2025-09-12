from ollama import Client, AsyncClient, GenerateResponse
from tempfile import TemporaryFile
from Utils.LogUtils import LogUtil
from Utils.ServerResponse import (
  ServerResponse,
  ServerResponseObject,
)


class LLMManager:
  def __init__(self, hostAddress: str, model='gemma3:1b'):
    self.client = Client(host=hostAddress)
    self.currentModel = model
    self.serverResponseUtil = ServerResponse('Ollama', 'ollama_log')

    # Logger
    self.log = LogUtil('LLM', 'llm_log')

  # --- Pulling Images ---
  def PullImage(self, imageName: str):
    result = self.client.pull(imageName)
    return self.serverResponseUtil.GenerateServerResponse(
      True, 'success', {'result': result}
    )

  # -- Switching models ---
  def SwitchModel(self, imageName: str):
    pass

  # --- Generating answers ---
  def Generate(self, prompt=''):
    pass

  # --- Deleting models ---
  def DeleteModel(self, modelName: str):
    pass

  # --- Get Models ---
  def GetModels(self):
    pass

  # --- helper functions ---
  def __GenerateResponse(
    self, success: bool, message: str, extraData: dict = {}, generateLog=True
  ):
    """
    Private helper function to keep return message code DRY.
    Handles generating log messages for the action.

    Args:
      success (
      bool): if the action was successful.
      message (str): the message to log and return
      extraData (dict): any extra information that should be returned
    Return:
      Object with both a result (bool) and message (str).
      Also returns extraData on the end if any passed.
    """
    if not success:
      if generateLog:
        self.log.GenerateLogMessage(message)
      return {'success': False, 'message': message, 'data': extraData}
    if generateLog:
      self.log.GenerateLogMessage(message)
    return {'success': True, 'message': message, 'data': extraData}
