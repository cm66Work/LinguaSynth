from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer


class DocumentHelper:
  @staticmethod
  def ExtractKeywords(content: str, frequency: float) -> list[str]:
    """
    Extracts the top keywords from the given content.
    Args:
        content (str): The content to extract the keywords from.
        frequency (float): Controls how often a keyword has to be present in the content before it is selected.

    Returns:
        list (list[str]): list of all extracted keywords from the content that appear a number of times equal too or more than the frequency.
    """
    countVectorizer = CountVectorizer(
      stop_words='english', max_df=0.9, min_df=2
    )
    paragraphs = [
      paragraphs.strip()
      for paragraphs in content.split('\n')
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
      if tup[2] > frequency:
        extractedKeywords.append(str(features[tup[1]]))
      # print('\n', features[tup[1]], tup[2])

    return extractedKeywords
