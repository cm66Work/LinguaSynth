import json
import os
from typing import List
from Managers.LLMManager import LLMManager, LLMServerResponseObject
from Utils import JsonUtils
from Utils.ServerResponse import ServerResponseObject
# from jsonschema import validate, ValidationError

# --- Constants ---
LLM_LIGHT_GENERATION_MODEL = 'gemma3:1b'  #'gemma3:1b-it-fp16'
# LLM_HEAVY_GENERATION_MODEL = 'gemma3:4b'
LLM_HEAVY_GENERATION_MODEL = 'gemma3:12b'
LLM_EMBEDDING_MODEL = 'embeddinggemma:300m'
LLM_EXAMPLE_SCHEMA_FIELDS = {
  'fields': [
    {'name': 'company_name', 'type': 'string'},
    {'name': 'num_employees', 'type': 'int32'},
    {'name': 'country', 'type': 'string', 'facet': 'true'},
  ],
}
SCHEMA_FIELDS_FORMAT = {
  'fields': {
    'company_name': {'type': 'string'},
    'year_created': {'type': 'integer'},
  }
}
LLM_SCHEMA_FILE_NAME = 'schema.txt'


class LLM_Object:
  def __init__(self):
    address = os.getenv('OLLAMA_ADDRESS', 'ollama')
    port = os.getenv('OLLAMA_PORT', '11434')
    self.client = LLMManager(hostAddress=f'{address}:{port}')

  async def Generate(self, prompt: str, think=False) -> LLMServerResponseObject:
    return await self.client.Generate(
      model=LLM_HEAVY_GENERATION_MODEL, prompt=prompt
    )

  # --- Handlers ---
  async def HandleSchemaGeneration(
    self, schemaName: str, content: str
  ) -> LLMServerResponseObject:
    """
    Generates a schema based on the provided base file.

    Args:
        content (str): the content to be summarized using the provided schema.

    Returns:

    """
    prompt = f"""
      You are given a sample document. Your task is to generate the "fields" section of a Typesense schema JSON based on the document.

      Rules:
      - Output ONLY a JSON object with a "fields" array.
      - Each element in "fields" must have:
        - "name": the field name as it appears in the document
      - Do not include example values, only field definitions.

      Example:
      Input document: To bake a cake requires the following ingredients: flower, eggs, water. This recipe is vegan, and it is rated at a difficulty of 3 out of 5 stars.
      Expected output:
      {{
        "fields": [
          {{"name": "title"}},
          {{"name": "ingredients"}},
          {{"name": "rating"}},
          {{"name": "is_vegan"}}
        ]
      }}

      Now generate the "fields" JSON for this document: {content}


      Generate at least 15 "fields"
      Only create height level abstracts fields that describe what each part means
    """
    result = await self.client.Generate(
      model=LLM_HEAVY_GENERATION_MODEL, prompt=prompt, think=False
    )
    response = JsonUtils.SanitizeJson(result.Response)
    response = json.loads(response[0])['fields']
    fields = []
    for field in response:
      fields.append(field['name'])

    prompt = f"""
    Rules:
      - Output strictly valid JSON (no comments, no trailing commas).
      - Each field object must include:
        - "type": one of [string, int32, int64, float, bool, string[]]
      - Use "string[]" if the value is an array of strings.
      - Use "int32" for small integers, "int64" for large integers.
      - Use "float" for decimals.
      - Use "bool" for true/false.

      For each filed in the list of fields given, output a list of data "types" that best match what they are tying to represent. for example: "year_created" would result in a data "type" of int32, where are "inventor" would result in a data "type" of string.

      Fields: {fields}
    """
    result = await self.client.Generate(
      model=LLM_HEAVY_GENERATION_MODEL,
      prompt=prompt,
      think=False,
    )
    sanitized, ok = JsonUtils.SanitizeJson(result.Response)
    if not ok:
      raise ValueError('SanitizeJson failed')
    response = json.loads(sanitized)

    schema = {'name': schemaName, 'fields': []}

    if isinstance(response, dict):
      # Dict form: { "field": "type" }
      for name, ftype in response.items():
        schema['fields'].append({'name': name, 'type': ftype})

    elif isinstance(response, list):
      # List form: [ {"field": ..., "type": ...}, ... ]
      for item in response:
        # Defensive: support both {"field":..,"type":..} and {"name":..,"type":..}
        field_name = item.get('field') or item.get('name')
        ftype = item.get('type', 'string')
        schema['fields'].append({'name': field_name, 'type': ftype})

    else:
      raise ValueError(f'Unexpected response type: {type(response)}')

    schema['fields'].append({'name': 'documentID', 'type': 'int64'})

    self.client.serverResponseUtil.GenerateLogMessage(
      messageString='new schema generated'
    )
    currentResponse = LLMServerResponseObject()
    currentResponse.Success = True
    currentResponse.Message = 'Generated new Schema'
    currentResponse.Response = json.dumps(schema)
    return self.client.serverResponseUtil.GenerateServerResponse(
      currentResponse
    )

  async def HandleContentSummarization(
    self, content: str, schemaFields
  ) -> LLMServerResponseObject:
    """
    Generates a summarized version of the content using the provided schema.

    Args:
        content (str): The content to be summarized using the provided schema.
        schema (str): The schema used to summarize the content.

    Returns:

    """
    result = await self.client.Generate(
      # Light model is two small to get good enough results at the moment.
      model=LLM_HEAVY_GENERATION_MODEL,
      prompt=f"""
      Schema fields:{json.dumps(schemaFields)}
      Document:{content}
      Summarize and match all content in the given document to all "name" key values based on their 'types'.
      Include as much single word detail as possible only.
      For each filed name match your result to its associated type. 
      """,
      # format=schemaFields,
    )
    return result

  async def GenerateV2(self, prompt: str, format={}) -> LLMServerResponseObject:
    result = await self.client.Generate(
      model=LLM_LIGHT_GENERATION_MODEL, prompt=prompt, format=format
    )
    return result

  async def GenerateV3(self, prompt: str, format={}) -> LLMServerResponseObject:
    result = await self.client.Generate(
      model=LLM_HEAVY_GENERATION_MODEL, prompt=prompt, format=format
    )
    return result

  async def GetEmbeddingsForContent(
    self, texts: List[str]
  ) -> List[List[float]]:
    return await self.client.GetEmbeddings(texts, LLM_EMBEDDING_MODEL)
