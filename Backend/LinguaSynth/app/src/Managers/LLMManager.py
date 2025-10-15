from dataclasses import dataclass
from typing import List, cast
from ollama import Client, ResponseError
from Utils.LogUtils import ErrorTypes
from Utils.ServerResponse import ServerResponse, ServerResponseObject


@dataclass
class LLMServerResponseObject(ServerResponseObject):
  Response: str = ''
  Streaming: bool = False


class LLMServerResponse(ServerResponse):
  def __init__(self, rootFolder: str, logBaseName: str):
    super().__init__(rootFolder, logBaseName)

  def GenerateServerResponse(  # type: ignore
    self,
    currentResponse: LLMServerResponseObject,
    className: str = '',
    errorType: ErrorTypes = ErrorTypes.Ok,
    generateLog=True,
    response: str = '',
  ):
    super().GenerateServerResponse(
      cast(ServerResponseObject, currentResponse),
      className,
      errorType,
      generateLog,
    )
    return currentResponse


class LLMManager:
  def __init__(self, hostAddress: str):
    self.client = Client(host=hostAddress)
    self.serverResponseUtil = LLMServerResponse('Ollama', 'ollama_log')

  # --- Pulling Images ---
  async def PullModel(self, imageName: str) -> LLMServerResponseObject:
    """
    Downloads the model if it exists on ollama's server.

    Args:
        imageName (str): The name of the image to pull.

    Returns:
        Returns a ServerResponseObject as the response.
    """
    currentResponse = LLMServerResponseObject()
    try:
      response = self.client.pull(imageName)
      currentResponse.Success = True
      currentResponse.Message = 'Pulled new ollama image.'
      currentResponse.Data = {'response': response}
      return self.serverResponseUtil.GenerateServerResponse(currentResponse)
    except ResponseError as e:
      currentResponse.Message = f'{e}'
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        errorType=ErrorTypes.Error,
        className=__class__.__name__,
      )

  # --- Generating answers ---
  async def Generate(
    self, model: str, prompt='', think=False, format={}
  ) -> LLMServerResponseObject:
    """
    Generation request to the current running LLM.

    Args:
        model (str): The model to use for generation.
        prompt (str): The prompt which is given to the LLM.

    Returns:
        Returns a ServerResponseObject as the response containing the generated answer.
    """
    currentResponse = LLMServerResponseObject()
    if len(prompt) <= 0:
      currentResponse.Message = 'prompt is empty.'
      currentResponse.Finished = True
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        errorType=ErrorTypes.Error,
        className=__class__.__name__,
      )
    if len(model) <= 0:
      currentResponse.Message = 'LLM model name is empty.'
      currentResponse.Finished = True
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        errorType=ErrorTypes.Error,
        className=__class__.__name__,
      )

    if not self.__ModelExists(model):
      await self.PullModel(imageName=model)

    try:
      result = ''
      if len(format) <= 0:
        result = self.client.generate(model=model, prompt=prompt, think=think)[
          'response'
        ]
      else:
        result = self.client.generate(
          model=model, prompt=prompt, think=think, format=format
        )['response']
      currentResponse.Success = True
      currentResponse.Message = 'Response generated.'
      currentResponse.Data = {'result': result}
      currentResponse.Response = result

      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse, generateLog=False
      )
    except ResponseError as e:
      currentResponse.Success = False
      currentResponse.Message = f'{e} {type(format)} {format}'
      currentResponse.Data = {'result': ''}
      currentResponse.Response = ''
      currentResponse.Finished = True

      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse, generateLog=False
      )

  def __ModelExists(self, modelName: str):
    models = self.client.list()
    if modelName in models:
      return True
    return False

  async def GetEmbeddings(
    self, texts: List[str], model: str
  ) -> List[List[float]]:
    """
    Get embeddings for a list of texts using your existing Ollama client class.

    Args:
        texts: List of text strings to embed.
        client: Your Ollama client instance that handles communication with the container.
        model: The embedding model name, default 'embeddinggemma:300m'.

    Returns:
        List of embedding vectors (List[List[float]]).
    """
    if not self.__ModelExists(model):
      await self.PullModel(imageName=model)
    embeddings = []

    for text in texts:
      try:
        response = self.client.embed(model=model, input=text)
        # Support different return shapes
        embeddings.append(response.embeddings)

      except Exception as e:
        print(f'[Warning] Embedding failed for text: {text[:50]}... ({e})')
        embeddings.append([])  # Empty vector fallback

    return embeddings
