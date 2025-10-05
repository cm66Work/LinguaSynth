import time
from Panels.Panel import Panel
from ButtonActions.ProcessUploadedDocuments import ProcessUploadedDocuments
from Utils.CustomTK import TextProgressBar


class ProcessNewUploadDocumentsPanel(Panel):
  def __init__(self, serverAddress, categoryName, progressbar: TextProgressBar):
    super().__init__(serverAddress, categoryName, progressbar)

  def ProcessNewUploadedDocuments(self):
    if not self.serverAddress or not self.categoryName:
      self.CreateMessageBox(
        'Server address and category are required!', self.ErrorType.Error
      )
      return

    def UpdateProgressbar(
      totalDocuments,
      processedDocuments,
      responseMessage,
      startTime,
    ):
      # compute ETA
      progressbarMessage = f'{responseMessage} | etc: Calculating...'
      if processedDocuments > 0:
        elapsed = time.time() - startTime
        rate = elapsed / processedDocuments
        remaining = rate * (totalDocuments - processedDocuments)

        mins, secs = divmod(int(remaining), 60)
        progressbarMessage = f'{responseMessage} | etr: {mins:02d}:{secs:02d}'

      # print(progressbarMessage)
      self.UpdateProgressbar(processedDocuments, totalDocuments, progressbarMessage)

    processor = ProcessUploadedDocuments(
      self.serverAddress, self.categoryName, progressBarCallback=UpdateProgressbar
    )
    result, statusCode = processor.ProcessFiles(startTime=time.time())
    # print('Final:', result, statusCode)

    self.CreateMessageBox(f'Result:{str(result)}', self.ErrorType.Info)
