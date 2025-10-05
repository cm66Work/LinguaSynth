# region Schema generation
import time
import tkinter as tk
from Panels.Panel import Panel
from ButtonActions.ProcessSchemaGeneration import ProcessSchemaGeneration
from Utils.CustomTK import TextProgressBar


class SchemaGenerationPanel(Panel):
  def __init__(
    self,
    sampleSize,
    resolution,
    serverAddress,
    categoryName,
    generatedSchema: tk.Entry,
    progressbar: TextProgressBar,
  ):
    super().__init__(serverAddress, categoryName, progressbar)

    self.schemaSampleSize = sampleSize.get().strip()
    self.schemaResolution = resolution.get().strip()
    self.generatedSchema = generatedSchema

  def GenerateSchema(self):
    if not self.serverAddress or not self.categoryName:
      self.CreateMessageBox(
        'server address and category are required!', self.ErrorType.Error
      )
      return

    def UpdateProgressbar(
      totalDocuments,
      processedDocuments,
      totalSchemaTags,
      processedSchemaTags,
      schemaJsonString,
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

      if processedSchemaTags > 0:
        elapsed = time.time() - startTime
        rate = elapsed / processedSchemaTags
        remaining = rate * (totalSchemaTags - processedSchemaTags)

        mins, secs = divmod(int(remaining), 60)
        progressbarMessage = f'{responseMessage} | etr: {mins:02d}:{secs:02d}'

      self.UpdateProgressbar(processedDocuments, totalDocuments, progressbarMessage)

    processor = ProcessSchemaGeneration(
      self.serverAddress,
      self.categoryName,
      self.schemaSampleSize,
      self.schemaResolution,
      progressBarCallback=UpdateProgressbar,
    )
    result, schemaJsonString = processor.GenerateSchema(time.time())
    # print('Final:', result, statusCode)

    # Hide progress bar when done
    # schemaProgressbarFrame.grid_forget()

    self.generatedSchema.insert(tk.INSERT, str(schemaJsonString))
    self.CreateMessageBox(
      'Tag generation completed. Please validate and confirm generated tags',
      self.ErrorType.Info,
    )
