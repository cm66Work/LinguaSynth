import json
import os
from Managers.LLMManager import LLMManager, LLMServerResponseObject
from Utils import JsonUtils
# from jsonschema import validate, ValidationError

# --- Constants ---
LLM_LIGHT_GENERATION_MODEL = 'gemma3:270m-it-bf16'  #'gemma3:1b-it-fp16'
# LLM_HEAVY_GENERATION_MODEL = 'gemma3:4b'
LLM_HEAVY_GENERATION_MODEL = 'gemma3:12b'
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
    self.client = LLMManager(
      hostAddress=f'{address}:{port}', model=LLM_LIGHT_GENERATION_MODEL
    )

  async def Generate(self, prompt: str, think=False) -> LLMServerResponseObject:
    return await self.client.Generate(model=LLM_HEAVY_GENERATION_MODEL, prompt=prompt)

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


      Generate at least 10 "fields"
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
    response = json.loads(JsonUtils.SanitizeJson(result.Response)[0])

    schema = {'name': schemaName, 'fields': []}
    for name, ftype in response.items():
      field_obj = {'name': name, 'type': ftype}
      schema['fields'].append(field_obj)

    schema['fields'].append({'name': 'documentID', 'type': 'int64'})
    schema['fields'].append({'name': 'article_name', 'type': 'string'})
    self.client.serverResponseUtil.GenerateLogMessage(
      messageString='new schema generated'
    )
    return self.client.serverResponseUtil.GenerateServerResponse(
      success=True, message='Generated new schema', response=json.dumps(schema)
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
      format=schemaFields,
    )
    return result

    # For example: {{'dessert_name': 'string'}} must be result in {{'dessert_name': 'cake'}}
    # For example: {{'first_appearance_year': 'int32'}} must be result in {{'first_appearance_year': 1900}}
    # Example output:
    # {{
    #   "id": "124",
    #   "company_name": "Stark Industries",
    #   "num_employees": 5215,
    #   "country": "USA"
    # }}

    # Output: JSON only.
