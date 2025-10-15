import json
import os
import re
from typing import List, cast
from Managers.LLMManager import LLMManager, LLMServerResponseObject
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils import JsonUtils
from typesense.types.collection import (
  CollectionSchema,
  RegularCollectionFieldSchema,
  ReferenceCollectionFieldSchema,
)
import numpy as np
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
    return await self.client.Generate(
      model=LLM_LIGHT_GENERATION_MODEL, prompt=prompt, format=format
    )

  async def GenerateV3(self, prompt: str, format={}) -> LLMServerResponseObject:
    result = await self.client.Generate(
      model=LLM_HEAVY_GENERATION_MODEL, prompt=prompt, format=format
    )
    return result


class EmbeddingVectorSchemaGenerator:
  def __init__(self, llmObject: LLM_Object, typesenseObject: Typesense_Object):
    self.llmObject: LLM_Object = llmObject
    self.typesenseObject: Typesense_Object = typesenseObject

  async def ReprocessSchema(
    self,
    currentSchema,
    document,
    confidenceThreshold: float = 0.01,
  ) -> CollectionSchema:
    try:
      currentSchema = cast(CollectionSchema, currentSchema)
      document = json.loads(document)
    except Exception:
      return currentSchema

    # candidate_fields = self.extract_field_candidates(document)
    candidate_fields = [entry['topic'] for entry in document]
    # pass this lower
    existing_field_names = [f['name'] for f in currentSchema['fields']]  # type: ignore

    all_texts = existing_field_names + candidate_fields
    if not all_texts:
      return currentSchema

    # check and remove similar fields from the schema.
    all_embeddings = await self.GetEmbeddingsForContent(all_texts)
    existing_embeds = all_embeddings[: len(existing_field_names)]
    candidate_embeds = all_embeddings[len(existing_field_names) :]

    refinedFields = list(currentSchema['fields'])

    for i, cand_embed in enumerate(candidate_embeds):
      cand_name = candidate_fields[i]

      if len(existing_embeds) > 0:
        similarities = self.cosine_similarity_np([cand_embed], existing_embeds)[
          0
        ]
        max_sim = float(np.max(similarities))
      else:
        max_sim = 0.0

      # remove the fields with low confidence thresholds
      if round(1 - max_sim, 3) < confidenceThreshold:
        continue  # field confidence is too low and its ignored.
      refinedFields.append(
        {
          'name': cand_name.lower().replace(' ', '_'),
          'type': 'string',
          # 'confidence': round(1 - max_sim, 3),
          # 'suggested': True,
        }
      )
    refinedFields = await self.deduplicate_fields(refinedFields)
    currentSchema['fields'] = cast(
      list[RegularCollectionFieldSchema | ReferenceCollectionFieldSchema],
      refinedFields,
    )
    currentSchema['name'] = (
      await self.llmObject.GenerateV2(
        f'Give the following json object a new or phrase which represents and outlines the information in the json object.\nJsonObject: {refinedFields}\n Answer only with the name limited to 10 words.'
      )
    ).Response

    def FilterName(schemaName: str) -> str:
      filterList = [':', ',', '.', '*', '\n', '/']
      for filter in filterList:
        schemaName = schemaName.replace(filter, '')
      schemaName = schemaName.replace(' ', '_')
      schemaName = schemaName.lower()
      return schemaName

    currentSchema['name'] = FilterName(currentSchema['name'])
    print(f'\n new schema: {currentSchema}')
    return currentSchema

  async def GetEmbeddingsForContent(
    self, texts: List[str]
  ) -> List[List[float]]:
    return await self.llmObject.client.GetEmbeddings(texts, LLM_EMBEDDING_MODEL)

  def cosine_similarity_np(self, a, b):
    """Same fixed version as before."""
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    if a.ndim > 2:
      a = a.reshape(a.shape[0], -1)
    if b.ndim > 2:
      b = b.reshape(b.shape[0], -1)
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return np.dot(a_norm, b_norm.T)

  async def deduplicate_fields(
    self, fields, threshold=0.96
  ) -> list[RegularCollectionFieldSchema | ReferenceCollectionFieldSchema]:
    names = [f['name'] for f in fields]
    embeddings = await self.GetEmbeddingsForContent(names)
    sim_matrix = self.cosine_similarity_np(embeddings, embeddings)

    keep = []
    removed = set()
    for i, name in enumerate(names):
      if name in removed:
        continue
      for j in range(i + 1, len(names)):
        if sim_matrix[i][j] > threshold:
          removed.add(names[j])
      keep.append(fields[i])
    return [f for f in keep if f['name'] not in removed]

  async def InferFieldType(
    self,
    field_name: str,
    field_context: str,
    llmObject,
    numberConfidenceThreshold: float = 0.85,
  ) -> str:
    """
    Infers whether a field should be a 'number' or 'string' based on its content and semantics.
    Uses regex heuristics and semantic similarity via embeddings.
    """

    # --- Step 1: Heuristic check for numeric pattern ---
    if re.fullmatch(
      r'[-+]?[0-9]*[.,]?[0-9]+(?:[eE][-+]?[0-9]+)?[%$kKmMbB]*',
      field_context.strip(),
    ):
      return 'number'

    # --- Step 2: Prepare embeddings for semantic similarity ---
    reference_terms = [
      'number',
      'numeric',
      'amount',
      'quantity',
      'value',
      'count',
    ]
    comparison_texts = [field_name] + reference_terms
    embeddings = await llmObject.GetEmbeddingsForContent(comparison_texts)

    field_embed = np.array(embeddings[0])
    ref_embeds = np.array(embeddings[1:])
    field_embed = field_embed.reshape(1, -1)
    ref_embeds = ref_embeds / np.linalg.norm(ref_embeds, axis=1, keepdims=True)
    field_embed = field_embed / np.linalg.norm(
      field_embed, axis=1, keepdims=True
    )
    sims = np.dot(field_embed, ref_embeds.T)[0]

    # --- Step 3: Threshold-based semantic decision ---
    if np.max(sims) > numberConfidenceThreshold:
      return 'number'
    return 'string'
