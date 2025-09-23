
def ConvertToJsonSchema(pseudo_schema: dict) -> dict:
    """
    Convert a pseudo-schema dict with types like 'int64', 'string[]'
    into a valid JSON Schema (Draft-07 style).
    """
    type_map = {
        "int32": {"type": "integer"},
        "int64": {"type": "integer"},
        "string": {"type": "string"},
        "float": {"type": "number"},
        "double": {"type": "number"},
        "boolean": {"type": "boolean"},
    }

    schema = {"type": "object", "properties": {}}

    for field, field_type in pseudo_schema.items():
        # Handle arrays like "string[]"
        if field_type.endswith("[]"):
            base_type = field_type.replace("[]", "")
            if base_type in type_map:
                schema["properties"][field] = {
                    "type": "array",
                    "items": type_map[base_type]
                }
            else:
                raise ValueError(f"Unsupported type: {field_type}")
        else:
            if field_type in type_map:
                schema["properties"][field] = type_map[field_type]
            else:
                raise ValueError(f"Unsupported type: {field_type}")

    return schema