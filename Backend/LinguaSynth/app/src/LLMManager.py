from ollama import Client, ResponseError
from Utils.ServerResponse import ServerResponse, ServerResponseObject


class LLMManager:
  def __init__(self, hostAddress: str, model='gemma3:1b'):
    self.client = Client(host=hostAddress)
    self.serverResponseUtil = ServerResponse('Ollama', 'ollama_log')

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
        True, 'Pulled new ollama image.', {'response': response}
      )
    except ResponseError as e:
      return self.serverResponseUtil.GenerateServerResponse(
        False, f'ERROR::LLMManager.PullImage:: {e}'
      )

  # --- Generating answers ---
  async def Generate(self, model: str, prompt=''):
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
      result = self.client.generate(model, prompt)
      return self.serverResponseUtil.GenerateServerResponse(
        True,
        'response generated',
        extraData={'response': result['response']},
        generateLog=False,
      )
    except ResponseError as e:
      return self.serverResponseUtil.GenerateServerResponse(
        False, f'ERROR::LLMManager.Generate:: {e}'
      )

  def __ModelExists(self, modelName: str):
    models = self.client.list()
    if modelName in models:
      return True
    return False
