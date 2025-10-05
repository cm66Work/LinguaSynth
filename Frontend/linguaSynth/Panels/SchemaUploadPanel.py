from tkinter import Entry
from Panels.Panel import Panel
from ButtonActions.UploadSchemaButtonAction import UploadSchemaButtonAction
from Utils.CustomTK import TextProgressBar


class SchemaUploadPanel(Panel):
  def __init__(
    self,
    serverAddress,
    categoryName,
    schemaJsonString: Entry,
    progressbar: TextProgressBar,
  ):
    super().__init__(serverAddress, categoryName, progressbar)

    self.schemaJsonString = schemaJsonString.get().strip()

  def UploadSchema(self):
    if not self.serverAddress or not self.categoryName:
      self.CreateMessageBox(
        'server address and category are required!', self.ErrorType.Error
      )
      return

    processor = UploadSchemaButtonAction(
      serverAddress=self.serverAddress,
      categoryName=self.categoryName,
      schemaJsonString=self.schemaJsonString,
      progressbarCallback=self.UpdateProgressbar,
    )
    success, serverResponse = processor.UploadSchema()

    if serverResponse is None or not success:
      self.CreateMessageBox(
        'Schema upload Failed. Please see log files for more information',
        self.ErrorType.Error,
      )
      return
    else:
      self.CreateMessageBox(
        'Schema Upload completed',
        self.ErrorType.Info,
      )
