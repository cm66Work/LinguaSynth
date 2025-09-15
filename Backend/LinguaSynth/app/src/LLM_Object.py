from LLMManager import LLMManager
import os

# --- Constants ---
LLM_LIGHT_GENERATION_MODEL = 'gemma3:1b-it-q8_0'
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

  async def HandleContentSummarization(self, content: str, schema: str) -> str:
    """
    Generates a summarized version of the content using the provided schema.

    Args:
        content (str): The content to be summarized using the provided schema.
        schema (str): The schema used to summarize the content.

    Returns:

    """
    result = await self.client.Generate(
      model=LLM_HEAVY_GENERATION_MODEL,
      prompt=f'{schema}. Use the provided schema to summarize the following content, only including what is necessary and relevant to each json schema category. document to summarize: {content}',
    )
    return result.Data['response']
