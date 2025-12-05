import json
from typing import cast
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.Typesense_Object import Typesense_Object
from Utils import CosignSimilarity
from typesense.types.collection import (
  CollectionSchema,
  RegularCollectionFieldSchema,
  ReferenceCollectionFieldSchema,
)
import numpy as np


class EmbeddingVectorSchemaGenerator:
  def __init__(self, llmObject: LLM_Object, typesenseObject: Typesense_Object):
    self.llmObject: LLM_Object = llmObject
    self.typesenseObject: Typesense_Object = typesenseObject

  async def ReprocessSchema(
    self,
    currentSchema: CollectionSchema,
    keywords: list[str],
    confidenceThreshold: float = 0.01,
  ) -> CollectionSchema:
    pass

  async def ReprocessSchema__Old(
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
    all_embeddings = await self.llmObject.GetEmbeddingsForContent(all_texts)
    existing_embeds = all_embeddings[: len(existing_field_names)]
    candidate_embeds = all_embeddings[len(existing_field_names) :]

    refinedFields = list(currentSchema['fields'])
    for i, cand_embed in enumerate(candidate_embeds):
      cand_name = candidate_fields[i]

      if len(existing_embeds) > 0:
        sims = CosignSimilarity.MultiVector([cand_embed], existing_embeds)[0]
        max_sim = float(np.max(sims))
      else:
        max_sim = 0.0

      if round(1 - max_sim, 3) < confidenceThreshold:
        continue

      refinedFields.append(
        {'name': cand_name.lower().replace(' ', '_'), 'type': 'string'}
      )
    refinedFields = await self.deduplicate_fields(refinedFields)
    currentSchema['fields'] = cast(
      list[RegularCollectionFieldSchema | ReferenceCollectionFieldSchema],
      refinedFields,
    )
    currentSchema['name'] = (
      await self.llmObject.Generate(
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
    return currentSchema

  async def deduplicate_fields(
    self, fields, threshold=0.96
  ) -> list[RegularCollectionFieldSchema | ReferenceCollectionFieldSchema]:
    names = [f['name'] for f in fields]
    embeddings = await self.llmObject.GetEmbeddingsForContent(names)
    sim_matrix = CosignSimilarity.MultiVector(embeddings, embeddings)

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
