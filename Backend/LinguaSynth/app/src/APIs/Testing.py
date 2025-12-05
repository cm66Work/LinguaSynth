import json
from typing import Any, Dict, List, Union

from ObjectInterfaces.LLM_Object import LLM_Object


class DocumentGenerator:
  def __init__(self, llmObject: LLM_Object):
    self.llm = llmObject

  async def GenerateDocument(
    self, collectionSchema, documentText: str
  ) -> Dict[str, Any]:
    """Main entry point"""
    return await self._generate_fields(
      collectionSchema.get('fields', []), documentText, path=[]
    )

  async def _generate_fields(
    self, fields: List[Dict[str, Any]], documentText: str, path: List[str]
  ) -> Dict[str, Any]:
    schema_doc = {}
    for field in fields:
      field_name = field['name']
      field_type = field['type']

      # context path for nested fields (useful in prompting)
      current_path = '.'.join(path + [field_name])
      value = await self._generate_field_value(
        field, documentText, current_path
      )
      schema_doc[field_name] = value

    return schema_doc

  async def _generate_field_value(
    self, field: Dict[str, Any], documentText: str, path: str
  ) -> Any:
    field_type = field['type']

    if field_type.endswith('[]'):
      # handle arrays
      base_type = field_type[:-2]
      prompt = f"From the following text, extract a list of {base_type} values for '{path}':\n\n{documentText}\n\nReturn as JSON list."
      raw_output = (await self.llm.Generate(prompt)).Response
      parsed = self._safe_parse_json(raw_output)

      if base_type == 'object':
        # recursively build each object
        nested_fields = field.get('fields', [])
        return [
          await self._generate_fields(
            nested_fields,
            json.dumps(item) if isinstance(item, dict) else documentText,
            path.split('.'),
          )
          for item in parsed
        ]
      else:
        # validate scalar array types
        return [
          await self._validate_type(base_type, item, path) for item in parsed
        ]

    elif field_type == 'object':
      nested_fields = field.get('fields', [])
      return await self._generate_fields(
        nested_fields, documentText, path.split('.')
      )

    else:
      prompt = (
        f"From the following text, extract the value for '{path}' as a {field_type}.\n"
        f'Respond with only a valid JSON literal (e.g. 123, "abc", true, etc):\n\n{documentText}'
      )
      raw_output = (await self.llm.Generate(prompt)).Response
      value = self._safe_parse_json(raw_output)
      return await self._validate_type(field_type, value, path)

  async def _validate_type(
    self, expected_type: str, value: Any, path: str
  ) -> Any:
    """Ensures that value matches the declared field type."""
    try:
      if expected_type == 'string':
        return str(value)
      elif expected_type == 'int':
        return int(value)
      elif expected_type == 'float':
        return float(value)
      elif expected_type == 'bool':
        return bool(value)
      else:
        return value
    except Exception:
      # fallback: ask LLM again for correct type
      correction_prompt = (
        f"The extracted value for '{path}' was invalid ({value}). "
        f'Please return a valid {expected_type} in strict JSON format only.'
      )
      corrected = (await self.llm.Generate(correction_prompt)).Response
      return self._safe_parse_json(corrected)

  def _safe_parse_json(self, text: str) -> Any:
    try:
      return json.loads(text)
    except Exception:
      # try to clean and parse again
      cleaned = text.strip().strip('`').replace('json', '')
      try:
        return json.loads(cleaned)
      except Exception:
        # final fallback to plain string
        return cleaned
