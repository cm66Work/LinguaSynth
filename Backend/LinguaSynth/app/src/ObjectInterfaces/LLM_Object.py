from Managers.LLMManager import LLMManager, LLMServerResponseObject
import os
# from jsonschema import validate, ValidationError

# --- Constants ---
LLM_LIGHT_GENERATION_MODEL = 'gemma3:270m-it-bf16'  #'gemma3:1b-it-fp16'
LLM_HEAVY_GENERATION_MODEL = 'gemma3:4b'
LLM_EXAMPLE_SCHEMA = {
  'name': 'companies',
  'num_documents': 0,
  'fields': [
    {'name': 'company_name', 'type': 'string'},
    {'name': 'num_employees', 'type': 'int32'},
    {'name': 'country', 'type': 'string', 'facet': 'true'},
  ],
  'default_sorting_field': 'num_employees',
}
LLM_SCHEMA_FILE_NAME = 'schema.txt'


class LLM_Object:
  def __init__(self):
    address = os.getenv('OLLAMA_ADDRESS', 'ollama')
    port = os.getenv('OLLAMA_PORT', '11434')
    self.client = LLMManager(
      hostAddress=f'{address}:{port}', model=LLM_LIGHT_GENERATION_MODEL
    )

  async def Generate(self, prompt: str) -> LLMServerResponseObject:
    return await self.client.Generate(model=LLM_HEAVY_GENERATION_MODEL, prompt=prompt)

  # --- Handlers ---
  async def HandleSchemaGeneration(self, content: str):
    """
    Generates a schema based on the provided base file.

    Args:
        content (str): the content to be summarized using the provided schema.

    Returns:

    """
    result = self.client.Generate(
      model=LLM_HEAVY_GENERATION_MODEL,
      prompt=f'{LLM_EXAMPLE_SCHEMA} \n Use the above Typesense schema template to generate a custom schema that will be used to later process related documents. Use the bellow base document to help focus the schema and include what is important. Base document: {content} \nOnly write the json output',
    )
    return await result

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
      Schema fields:{schemaFields}
      Document:{content}
      Summarize and match all content in the given document to all "name" key values based on their 'types'.
      Include as much single word detail as possible only.
      For each filed name match your result to its associated type. 
      For example: {{'dessert_name': 'string'}} must be result in {{'dessert_name': 'cake'}}
      For example: {{'first_appearance_year': 'int32'}} must be result in {{'first_appearance_year': 1900}}
      Example output:
      {{
        "id": "124",
        "company_name": "Stark Industries",
        "num_employees": 5215,
        "country": "USA"
      }}

      Output: JSON only.
      """,
    )
    return result

  # f'{schemaFields}. \nUse the provided schema fields to summarize the following content, only including what is necessary and relevant to each field. Including only all "name" keys from the fields in your response is critical. \nDocument to summarize: {content}. \n respond with json only',

  #  You are a query generator. Convert a user question into a valid Typesense search query JSON.

  #   Rules:
  #   - Only include string or string[] fields in "query_by".
  #   - Use numeric or date fields only in "filter_by" or "sort_by".
  #   - Always return only JSON, no explanations.

  #   Example:
  #   Q: "Find books by Isaac Asimov"
  #   A:
  #   {{
  #   'q': "Isaac Asimov",
  #     "query_by": "author",
  #     "filter_by": "year:>2010",
  #   }}

  #   Q: "science fiction novels after 2010"
  #   A:
  #   {{
  #   'q': "science fiction",
  #     "query_by": "genre,title,summary"
  #     "filter_by": "year:>2010",
  #     "sort_by": "year:desc",
  #   }}

  #   Schema fields:
  #   {fieldsNames}

  #   User question:
  #   {userQuestion}

  #   Generate the correct Typesense query JSON:
  #   You must include q, query_by, and filter_by in your response.
  #   You must include q, query_by, and filter_by in your response.
