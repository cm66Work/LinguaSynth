import json
import re


def ConvertToJsonSchema(pseudo_schema: dict) -> str:
  """
  Convert a pseudo-schema dict with types like 'int64', 'string[]'
  into a valid JSON Schema (Draft-07 style).
  """
  type_map = {
    'int32': {'type': 'integer'},
    'int64': {'type': 'integer'},
    'string': {'type': 'string'},
    'float': {'type': 'number'},
    'double': {'type': 'number'},
    'boolean': {'type': 'boolean'},
  }

  schema = {'type': 'object', 'properties': {}}

  for field, field_type in pseudo_schema.items():
    # Handle arrays like "string[]"
    if field_type.endswith('[]'):
      base_type = field_type.replace('[]', '')
      if base_type in type_map:
        schema['properties'][field] = {'type': 'array', 'items': type_map[base_type]}
      else:
        raise ValueError(f'Unsupported type: {field_type}')
    else:
      if field_type in type_map:
        schema['properties'][field] = type_map[field_type]
      else:
        raise ValueError(f'Unsupported type: {field_type}')

  return json.dumps(schema)


def SanitizeJson(content: str):
  """
  Extracts the first JSON object from text and normalizes
  it into a single-line valid JSON string.
  """
  # Grab first {...} block or the first list of {}.
  match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', content)
  if not match:
    return ['', False]

  content = match.group(0)
  content = content.replace('\\n', '')
  content = content.replace("'", '"')
  print(content)
  # Normalize schema (handles double-encoded JSON too)
  try:
    parsed = json.loads(
      json.loads(content) if content.strip().startswith("'") else content
    )
    return [json.dumps(parsed, separators=(',', ':')), True]
  except Exception as e:
    # Return an empty string + False instead of the Exception object
    print(e)
    return [f'{e}', False]
