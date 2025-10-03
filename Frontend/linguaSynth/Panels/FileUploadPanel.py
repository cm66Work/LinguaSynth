import math
import os
from tkinter import messagebox
import threading

from ButtonActions import UploadFile
from Utils.CustomTK import TextProgressBar


class FileUploadPanel:
  def __init__(
    self, rootDirectory, serverAddress, categoryEntry, progressbar: TextProgressBar
  ):
    self.rootDirectory = rootDirectory
    self.serverAddress = serverAddress
    self.categoryEntry = categoryEntry
    self.progressbar = progressbar

  def upload_files(self):
    # Run upload in a background thread so GUI stays responsive
    threading.Thread(target=self.__UploadFileThread, daemon=True).start()

  def __UploadFileThread(self):
    directory = self.rootDirectory.get().strip()
    server_address = self.serverAddress.get().strip()
    category = self.categoryEntry.get().strip()

    if not directory or not server_address or not category:
      messagebox.showerror('Error', 'All fields are required!')
      return

    if not os.path.isdir(directory):
      messagebox.showerror('Error', f'{directory} is not a valid directory')
      return

    txt_files = [f for f in os.listdir(directory) if f.endswith('.txt')]
    if not txt_files:
      messagebox.showinfo('Info', 'No .txt files found in directory.')
      return

    # Show progress bar

    def update_progress(current, total):
      percentage = math.ceil((current / total) * 100)
      self.progressbar.SetProgress(percentage)

    # Use the uploader class
    uploader = UploadFile.FileUploader(
      directory=directory,
      server_address=server_address,
      category=category,
      progress_callback=update_progress,
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
