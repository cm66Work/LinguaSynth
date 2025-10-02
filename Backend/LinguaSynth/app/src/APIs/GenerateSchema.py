from dataclasses import asdict
import difflib
import json
import math

from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils.LogUtils import ErrorTypes
from Utils import JsonUtils
from fastapi.responses import StreamingResponse


async def SchemaGeneration(
  bucketRootName: str,
  sampleSize: int,
  serverResponse: ServerResponse,
  minioObject: MinIO_Object,
  llmObject: LLM_Object,
  resolution: int = 1,
  force: bool = False,
  tagCompression: float = 0.25,
) -> StreamingResponse:
  """

  Args:
      bucketRootName: str
      sampleSize: int
      resolution: int = 1
      force: bool = False
      tagCompression:float = 0.25 : tag similarity matching for quote combining.
  """
  returnedDataObject = {
    'total_documents_to_process': -1,
    'processed_document_count': -1,
    'total_schema_tags': -1,
    'processed_schema_tags': -1,
    'schema_json_string': '',
  }
  currentResponse = serverResponse.GenerateServerResponse(
    success=True,
    message='',
    extraData=returnedDataObject,
    finished=False,
  )

  async def EventStream():
    currentResponse.Message = 'Processing...'
    yield json.dumps(vars(currentResponse))

    if len(bucketRootName) <= 0:
      yield json.dumps(
        asdict(
          serverResponse.GenerateServerResponse(
            success=False,
            message='Bucket root name has not been provided',
            extraData=returnedDataObject,
            errorType=ErrorTypes.Error,
            className='main',
            finished=True,
          )
        )
      )
      return

    # Check if there are files in the processed bucket
    bucketName = f'{bucketRootName}-processed'
    documentsToSkip = math.floor(
      minioObject.GetNumberOfObjectsInBucket(bucketName) / sampleSize
    )
    if documentsToSkip <= 0:
      yield json.dumps(
        asdict(
          serverResponse.GenerateServerResponse(
            success=False,
            message=f'No documents loaded into bucket: {bucketName}',
            extraData=returnedDataObject,
            errorType=ErrorTypes.Warning,
            className='main',
            finished=True,
          )
        )
      )
      return

    # Grab a random number of files based on the given random number.
    # - random spread against the total number of files.
    returnedDataObject['total_documents_to_process'] = documentsToSkip
    returnedDataObject['processed_document_count'] = 0
    currentResponse.Message = f'Identifying tags from: {resolution} document(s) ...'
    yield json.dumps(vars(currentResponse))

    documentTags: list[dict[str, str]] = []
    skippedDocuments = documentsToSkip
    for document in minioObject.GetObjectsInBucket(bucketName):
      skippedDocuments -= 1
      if skippedDocuments > 0:
        continue  # skip this document
      skippedDocuments = documentsToSkip  # rest the skip count

      if document.object_name is None:
        continue
      documentContent: str = minioObject.GetContentOfBucketObject(
        bucketName, document.object_name
      ).Data['content']
      # Recursive run against all paragraphs for each document.
      # - Return should be the tag and the value or quote related to it.
      documentTags.extend(
        await __GenerateTagsFromDocument(
          content=documentContent, resolution=resolution, llmObject=llmObject
        )
      )
      # Reduce the number of tags
      # - join values or quotes if we remove a duplicate.
      # -- Might be fun to see if there is a way to generate tags through logic.
      documentTags = reduce_tags_fuzzy(documentTags, 0.2)

      returnedDataObject['processed_document_count'] += 1
      currentResponse.Message = (
        f'Processing... | Identified {len(documentTags)} unique tags...'
      )
      yield json.dumps(vars(currentResponse))

    # Parse the tags against the values / quotes to get their json types.
    # - Our schema object will handle the conversion to Typesense.

    returnedDataObject['processed_schema_tags'] = 0
    returnedDataObject['total_schema_tags'] = len(documentTags)
    currentResponse.Message = 'Processing Tags...'
    yield json.dumps(vars(currentResponse))

    processedTags: list[dict[str, str]] = []
    for tag in documentTags:
      processedTags.extend(await _GenerateJsonTypeForTag(tag, llmObject))
      currentResponse.Message = f'Processing {len(processedTags)}/{len(tag)} Tags...'

      returnedDataObject['processed_schema_tags'] += 1
      yield json.dumps(vars(currentResponse))

    currentResponse.Message = f'Finished Processing {len(processedTags)} Tags...'
    returnedDataObject['schema_json_string'] = json.dumps(processedTags)
    yield json.dumps(vars(currentResponse))

    # Return the final Generated Schema for user review
    # -- Give users the option to check what was generated,
    # -- since we for sure need to remove random AI BS
    return

  return StreamingResponse(EventStream(), media_type='application/json')


async def _GenerateJsonTypeForTag(tag: dict[str, str], llmObject: LLM_Object):
  # Use AI to figure out json type bests matches the quote or quotes,
  # using the tag as the context to help guild the AI to the best answer.
  # input -> {"tag": "tag", "quote": "quote1 | quite 2" }
  # output -> {"name": "name", "type": "String or Number Or Array so on"}
  response = await llmObject.GenerateV2(
    f"""
    tag: {tag} 
    Based on the given tag's "quote", identify which word "String" or "Number" would best fit the quoted text. For example if the quote is "built in 1997" then the type value would be "Number", or if the quote is "owner is john dow" then the type would be"String".
    Return should be in json format: {{"tag":"tagName", "type":"String or Number"}}
    Only return valid JSON.
    """
  )

  # convert to 1 line to make the converter ore accurate.
  result = ' '.join(line.strip() for line in response.Response.splitlines())
  return json.loads(JsonUtils.TryConvertStringToJson(result))['matches']


async def __GenerateTagsFromDocument(
  content: str,
  resolution: int,
  llmObject: LLM_Object,
  existingTags: list[dict[str, str]] = [],
) -> list[dict[str, str]]:
  """
  Summarizes content into a JSON list of {tag, quote} objects, with recursion based on the resolution.
  """
  for paragraph in content.splitlines():
    if not paragraph.strip():
      continue
    response = await llmObject.GenerateV2(
      f"""paragraph: {paragraph} 
            Summarize the content of this paragraph into a JSON list of tags. 
            Format per item: {{"tag": "string", "quote": "string"}}. 
            Summarize the "quote" to ~10 words. 
            Only return valid JSON."""
    )
    result = ' '.join(line.strip() for line in response.Response.splitlines())
    generated = json.loads(JsonUtils.TryConvertStringToJson(result))
    if not generated:
      continue

    def __flatten_tags(nested):
      """
      Flattens a nested set of tags and returns a list of tags with a depth of 1
      [[[[]]]] -> []
      """
      flat = []
      for item in nested:
        if isinstance(item, list):
          flat.extend(__flatten_tags(item))  # recursion.
        elif isinstance(item, dict):
          flat.append(item)
      return flat

    existingTags.extend(__flatten_tags(generated['matches']))
  resolution -= 1
  if resolution > 0:
    return await __GenerateTagsFromDocument(content, resolution, llmObject, existingTags)

  return existingTags


def reduce_tags_fuzzy(
  tags: list[dict[str, str]], cutoff: float = 0.8
) -> list[dict[str, str]]:
  """Merge tags that are similar based on fuzzy string matching."""
  reduced = []

  for item in tags:
    tag = item['tag'].strip().lower()
    matched = False

    for existing in reduced:
      ratio = difflib.SequenceMatcher(None, tag, existing['tag']).ratio()
      if ratio >= cutoff:
        existing['quote'] += ' | ' + item['quote']
        matched = True
        break

    if not matched:
      reduced.append({'tag': tag, 'quote': item['quote']})

  return reduced
