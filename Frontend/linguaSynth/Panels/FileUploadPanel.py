import os
from tkinter import messagebox
import threading

from ButtonActions import UploadFile
from Panels.Panel import Panel
from Utils.CustomTK import TextProgressBar


class FileUploadPanel(Panel):
  def __init__(
    self, rootDirectory, serverAddress, categoryName, progressbar: TextProgressBar
  ):
    super().__init__(serverAddress, categoryName, progressbar)
    self.rootDirectory = rootDirectory.get().strip()

  def UploadFiles(self):
    # Run upload in a background thread so GUI stays responsive
    threading.Thread(target=self.__UploadFileThread, daemon=True).start()

  def __UploadFileThread(self):
    directory = self.rootDirectory
    serverAddress = self.serverAddress
    category = self.categoryName

    if not directory or not serverAddress or not category:
      self.CreateMessageBox('All fields are required!', self.ErrorType.Error)
      return

    if not os.path.isdir(directory):
      self.CreateMessageBox(f'{directory} is not a valid directory', self.ErrorType.Error)
      return

    txt_files = [f for f in os.listdir(directory) if f.endswith('.txt')]
    if not txt_files:
      self.CreateMessageBox('No .txt files found in directory.', self.ErrorType.Info)
      return

    # Use the uploader class
    uploader = UploadFile.FileUploader(
      directory=directory,
      server_address=serverAddress,
      category=category,
      progress_callback=self.UpdateProgressbar,
    )
    uploaded, failed = uploader.upload_all()

    # Hide progress bar
    # progressbar_frame.grid_forget()

    result_msg = (
      f'Uploaded: {uploaded}\nFailed: {failed}'
      if failed
      else f'All files uploaded successfully: {uploaded}'
    )
    messagebox.showinfo('Upload Result', result_msg)
