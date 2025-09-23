from dataclasses import dataclass
from ollama import Client, ResponseError
from Utils.LogUtils import ErrorTypes
from Utils.ServerResponse import ServerResponse, ServerResponseObject


@dataclass
class LLMServerResponseObject(ServerResponseObject):
  Response: str
  Streaming: bool = False


class LLMServerResponse(ServerResponse):
  def __init__(self, rootFolder: str, logBaseName: str):
    super().__init__(rootFolder, logBaseName)

  def GenerateServerResponse(
    self,
    success: bool,
    message: str = '',
    className: str = '',
    errorType: ErrorTypes = ErrorTypes.Ok,
    extraData: dict = {},
    response: str = '',
    generateLog=True,
  ):
    if generateLog or len(message) > 0:
      self.GenerateLogMessage(message, className=className, errorType=errorType)
    return LLMServerResponseObject(
      Success=success, Message=message, Data=extraData, Response=response
    )


class LLMManager:
  def __init__(self, hostAddress: str, model='gemma3:1b'):
    self.client = Client(host=hostAddress)
    self.serverResponseUtil = LLMServerResponse('Ollama', 'ollama_log')

  # --- Pulling Images ---
  async def PullModel(self, imageName: str) -> ServerResponseObject:
    """
    Downloads the model if it exists on ollama's server.

    Args:
        imageName (str): The name of the image to pull.

    Returns:
        Returns a ServerResponseObject as the response.
    """
    try:
      response = self.client.pull(imageName)
      return self.serverResponseUtil.GenerateServerResponse(
        success=True, message='Pulled new ollama image.', extraData={'response': response}
      )
    except ResponseError as e:
      return self.serverResponseUtil.GenerateServerResponse(
        False, f'ERROR::LLMManager.PullImage:: {e}'
      )

  # --- Generating answers ---
  async def Generate(self, model: str, prompt='', think=False, format={}) -> LLMServerResponseObject:
    """
    Generation request to the current running LLM.

    Args:
        model (str): The model to use for generation.
        prompt (str): The prompt which is given to the LLM.

    Returns:
        Returns a ServerResponseObject as the response containing the generated answer.
    """
    if len(prompt) <= 0:
      return self.serverResponseUtil.GenerateServerResponse(
        False, 'ERROR::LLMManager.Generate:: Prompt is empty.'
      )
    if model == '':
      return self.serverResponseUtil.GenerateServerResponse(
        False, 'ERROR::LLMManager.Generate:: LLM model name is empty.'
      )

    if not self.__ModelExists(model):
      await self.PullModel(imageName=model)

    try:
      result = ''
      if len(format) <= 0:
        result = self.client.generate(
          model=model, prompt=prompt, think=think 
        )
      else:
        result = self.client.generate(
          model=model, prompt=prompt, think=think, format=format 
        )
      return self.serverResponseUtil.GenerateServerResponse(
        True,
        'response generated',
        # extraData={'response': result['response']},
        response=result['response'],
        extraData={'result': result},
        generateLog=False,
      )
    except ResponseError as e:
      return self.serverResponseUtil.GenerateServerResponse(
        False, f'ERROR::LLMManager.Generate:: {e} {type(format)} {format}'
      )

  def __ModelExists(self, modelName: str):
    models = self.client.list()
    if modelName in models:
      return True
    return False
