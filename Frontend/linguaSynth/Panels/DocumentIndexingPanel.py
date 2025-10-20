from Panels.Panel import Panel
from Utils.CustomTK import TextProgressBar
from ButtonActions.DocumentIndexingButtonAction import DocumentIndexingButtonAction


class DocumentIndexingPanel(Panel):
  def __init__(
    self,
    serverAddress,
    categoryName,
    progressbar: TextProgressBar,
  ):
    super().__init__(serverAddress, categoryName, progressbar)

  def StartIndexingDocuments(self):
    if not self.serverAddress or not self.categoryName:
      self.CreateMessageBox(
        'server address and category are required!', self.ErrorType.Error
      )
      return

    processor = DocumentIndexingButtonAction(
      serverAddress=self.serverAddress,
      categoryName=self.categoryName,
      progressbarCallback=self.UpdateProgressbar,
    )
    success, serverResponse = processor.StartIndexingDocuments()

    if serverResponse is None or not success:
      self.CreateMessageBox(
        'Please see log files for more information',
        self.ErrorType.Error,
      )
      return
    else:
      self.CreateMessageBox(
        'Indexing completed',
        self.ErrorType.Info,
      )
