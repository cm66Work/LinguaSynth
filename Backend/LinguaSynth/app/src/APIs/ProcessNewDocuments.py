import json
import re
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from typing import List
from APIs.UploadProcessedDocuments import UploadProcessedDocuments
from ObjectInterfaces.MinIO_Object import MinIO_Object
from ObjectInterfaces.LLM_Object import LLM_Object
from ObjectInterfaces.PostgresObject import Postgres_Object
from Utils import CosignSimilarity, JsonUtils
from Utils.ServerResponse import ServerResponse, ServerResponseObject
from Utils.LogUtils import ErrorTypes


# region Document summarization and processing
# Process all original documents to summarized formats.
# is later used to indexing into Typesense.
async def ProcessNewDocuments(
  bucketRootName: str,
  serverResponse: ServerResponse,
  minioObject: MinIO_Object,
  llmObject: LLM_Object,
  postgresObject: Postgres_Object,
  frequencyThreshold: float = 0.25,
):
  extraData = {
    'document_count': 0,
    'processed_document_count': 0,
    'DocumentNames': '',
  }
  currentResponse = ServerResponseObject()
  currentResponse.Data = extraData
  currentResponse.Message = 'Processing....'

  # summarize all documents in the target category,
  # and save the results into a separate bucket.
  # We do not need typesense to process entire documents for indexing and document generation.
  # We need to reduce the amount of data that is bing processed by Typesense.
  newDocumentBucketName = f'{bucketRootName}-new'
  if not await minioObject.BucketExists(newDocumentBucketName):
    currentResponse.Message = (
      f'No bucket with name: {newDocumentBucketName} found.'
    )
    currentResponse.Finished = True
    yield serverResponse.GenerateServerResponse(
      currentResponse,
      className=__name__,
      errorType=ErrorTypes.Error,
    )
    return
  # send off the number of documents in the bucket.
  documentCount = minioObject.GetNumberOfObjectsInBucket(newDocumentBucketName)
  currentResponse.Data['document_count'] = documentCount
  yield serverResponse.GenerateServerResponse(currentResponse)

  uploadedDocumentNames = []
  unprocessedDocumentNames = []
  mergedContent: list[str] = []
  # Get all original documents in the storage bucket.
  for document in minioObject.GetObjectsInBucket(newDocumentBucketName):
    currentResponse.Message = 'Processing...'
    currentResponse.Data['processed_document_count'] = len(
      uploadedDocumentNames
    ) + len(unprocessedDocumentNames)

    yield serverResponse.GenerateServerResponse(currentResponse)
    # For each document, generate summarized document
    if document.object_name is None:
      serverResponse.GenerateLogMessage(
        messageString=f'Tried to process a document with no name from bucket: {newDocumentBucketName}, skipping file.'
      )
      unprocessedDocumentNames.append(document.object_name)
      continue
    result = minioObject.GetContentOfBucketObject(
      newDocumentBucketName, document.object_name
    )
    if not result.Success:
      serverResponse.GenerateLogMessage(
        messageString=f'Failed to get content from file: {document.object_name.split(".")[0]}, from bucket: {newDocumentBucketName}, skipping file.'
      )

      unprocessedDocumentNames.append(document.object_name)
      continue
    originalContent = result.Data['content']

    countVectorizer = CountVectorizer(
      stop_words='english', max_df=0.9, min_df=2
    )
    paragraphs = [
      paragraphs.strip()
      for paragraphs in originalContent.split('\n')
      if len(paragraphs) > 0
    ]
    wordCount = countVectorizer.fit_transform(paragraphs)
    features = countVectorizer.get_feature_names_out()

    transformer = TfidfTransformer()
    transformer.fit(wordCount)

    countVector = countVectorizer.transform(paragraphs)
    tfidfVector = (transformer.transform(countVector)).tocoo()  # type: ignore
    tuples = zip(tfidfVector.row, tfidfVector.col, tfidfVector.data)

    tfidfVector = sorted(tuples, key=lambda x: x[2], reverse=True)
    extractedKeywords: list[str] = []
    for tup in tfidfVector:
      if tup[2] > frequencyThreshold:
        extractedKeywords.append(str(features[tup[1]]))
      # print('\n', features[tup[1]], tup[2])

    # Upload summarized document into their own bucket and store a reference in the database table.
    # story both the original document path and the summarized document path.
    summarizedDocumentName = (
      f'{document.object_name.split(".")[0]}-summarized.txt'
    )
    summarizedBucketName = f'{bucketRootName}-summarized'

    result = await UploadProcessedDocuments(
      f'{bucketRootName}-processed',
      summarizedBucketName,
      originalContent,
      str(extractedKeywords)[1:-1],
      f'{document.object_name.split(".")[0]}-processed.txt',
      summarizedDocumentName,
      serverResponse=serverResponse,
      minioObject=minioObject,
      postgresObject=postgresObject,
    )
    if not result.Success:
      serverResponse.GenerateLogMessage(
        messageString=f'failed to upload: {document.object_name}, skipping file.'
      )
      unprocessedDocumentNames.append(document.object_name)
      continue
    serverResponse.GenerateLogMessage(
      messageString=f'document: {document.object_name} has been processed successfully.'
    )
    uploadedDocumentNames.append(document.object_name)

    # move the document from the new bucket to the processed bucket
    minioObject.DeleteDocument(document.object_name, newDocumentBucketName)
    currentResponse.Success = len(uploadedDocumentNames) > 0
    currentResponse.Message = (
      f'finished uploading {len(uploadedDocumentNames)} documents'
    )
    currentResponse.Data['DocumentNames'] = uploadedDocumentNames
    currentResponse.Data['document_count'] = documentCount
    currentResponse.Data['processed_document_count'] = len(
      uploadedDocumentNames
    ) + len(unprocessedDocumentNames)
    currentResponse.Finished = True
    yield serverResponse.GenerateServerResponse(currentResponse)


async def SummarizeToKeyIdentifiers(
  content: str,
  context: str,
  llmObject: LLM_Object,
):
  """
  Focuses on summarizing the document to detect names, key items, or people
  Args:
      content: str : The content to be summarized
      context: str : The context used to guide the LLM when summarizing the document.
      llmObject: LLM_Object : the llm object that will be used to summarize the document.
  """
  summarizedContent = []
  for paragraph in content.split('\n\n'):
    if len(paragraph) <= 0:
      continue
    llmResponse = await llmObject.Generate(
      f"""paragraph: {paragraph} \nUse the following context: {context}: identify key items, people, names, statistics, or figures from the paragraph into a JSON list of {{"topic": "topic name", "quote":"quote from paragraph"}}. Respond with only valid JSON."""
    )
    if not llmResponse.Success:
      continue
    # strip and process into json
    llmResponse = json.loads(
      JsonUtils.TryConvertStringToJson(llmResponse.Response)
    )
    for match in llmResponse['matches']:
      try:
        summarizedContent.append(
          {'topic': match['topic'], 'quote': match['quote']}
        )
      except Exception:
        pass

  return summarizedContent


# Very basic tokenizer to extract candidate keywords
_WORD_RE = re.compile(r'\b\w+\b', re.UNICODE)

_STOPWORDS = {
  'the',
  'a',
  'an',
  'and',
  'or',
  'of',
  'to',
  'in',
  'on',
  'for',
  'with',
  'at',
  'by',
  'from',
  'as',
  'is',
  'it',
  'that',
  'this',
  'these',
  'those',
  'be',
  'are',
  'was',
  'were',
  'has',
  'have',
  'had',
  'not',
  'but',
  'if',
  'then',
  'so',
  'than',
  'too',
  'very',
  'can',
  'may',
  'might',
  'shall',
  'will',
  'would',
  'could',
  'should',
  'do',
  'does',
  'did',
}


def ExtractCandidateKeywords(text: str) -> List[str]:
  """
  Returns a list of uniq words from the given text.
  Input: "The river runs along the valley and the morning light softens everything."
  Output: ["river", "runs", "along", "valley", "morning", "light", "softens", "everything"]
  """
  tokens = _WORD_RE.findall(text.lower())
  candidates = set()

  for t in tokens:
    if len(t) < 3:
      continue
    if t in _STOPWORDS:
      continue
    candidates.add(t)

  return list(candidates)


async def SummarizeDocument(
  content: str,
  context: list[str],
  llmObject: LLM_Object,
  top_k: int = 25,
) -> List[str]:
  """
  Uses embeddings to extract keywords from `content` that are most similar to `context`.

  Args:
      content: The full text content to extract keywords from.
      context: File or folder name, used as the semantic reference.
      llmObject: Object that exposes `GetEmbeddings(texts: List[str], model: str)`.
      top_k: Number of top matching keywords to return.

  Returns:
      List of keywords sorted by similarity to `context` (highest first).
  """

  # Collect candidate keywords from the entire content
  candidate_keywords = ExtractCandidateKeywords(content)

  if not candidate_keywords:
    return []

  # First embedding is the context, followed by one embedding for each keyword
  texts_for_embedding = context + candidate_keywords
  # print(texts_for_embedding)

  embeddings = await llmObject.GetEmbeddingsForContent(texts_for_embedding)

  if not embeddings or len(embeddings) != len(texts_for_embedding):
    return []

  context_embedding = embeddings[0]
  keyword_embeddings = embeddings[1:]

  # Compute similarity per keyword
  scored_keywords = []
  for keyword, emb in zip(candidate_keywords, keyword_embeddings):
    score = CosignSimilarity.SingleVector(context_embedding, emb)
    scored_keywords.append((keyword, score))

  # Sort by similarity score descending
  scored_keywords.sort(key=lambda x: x[1], reverse=True)

  # Return just the keywords, top_k capped by available length
  top_k = min(top_k, len(scored_keywords))
  return [kw for kw, _ in scored_keywords[:top_k]]


async def SummarizeDocument__OLD(
  content: str,
  context: str,
  llmObject: LLM_Object,
):
  """
  Summarizes the given content's paragraphs content by the resolution
  For example if a resolution of 2 is given, then each paragraph of the content will be summarized twice.

  Args:
      content: str : The content to be summarized
      context: str : The context used to guide the LLM when summarizing the document.
      llmObject: LLM_Object : the llm object that will be used to summarize the document.
  """
  summarizedContent = []
  for paragraph in content.split('\n\n'):
    if len(paragraph) <= 0:
      continue
    # summarizedParagraph = await llmObject.GenerateV2(
    #   f"""paragraph: {paragraph} \n summarize the paragraph into 75% of its original length using the context: {context}. Only reply with the summarized content and do not write anything else or respond to this prompt."""
    # )
    llmResponse = await llmObject.Generate(
      f"""paragraph: {paragraph} \nUse the following context: {context}: To summarize and format the paragraph into a JSON list of {{"topic": "topic name", "quote":"quote from paragraph"}}. Respond with only valid JSON."""
    )
    if not llmResponse.Success:
      continue
    # strip and process into json
    llmResponse = json.loads(
      JsonUtils.TryConvertStringToJson(llmResponse.Response)
    )
    for match in llmResponse['matches']:
      try:
        summarizedContent.append(
          {'topic': match['topic'], 'quote': match['quote']}
        )
      except Exception:
        pass

  return summarizedContent
