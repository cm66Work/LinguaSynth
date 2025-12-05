from enum import Enum
import math
from tkinter import messagebox
from Utils.CustomTK import TextProgressBar


class Panel:
  def __init__(self, serverAddress, categoryName, progressbar: TextProgressBar):
    self.serverAddress = serverAddress.get().strip()
    self.categoryName = categoryName.get().strip()
    self.progressbar = progressbar

  class ErrorType(Enum):
    Error = 'Error'
    Warning = 'Warning'
    Info = 'Info'

  def CreateMessageBox(self, message: str, errorType: ErrorType):
    match errorType:
      case self.ErrorType.Error:
        messagebox.showerror(errorType.value, message)
      case self.ErrorType.Warning:
        messagebox.showwarning(errorType.value, message)
      case self.ErrorType.Info:
        messagebox.showinfo(errorType.value, message)

  def UpdateProgressbar(self, current, total, message: str = ''):
    if total <= 0:
      return
    percentage = math.ceil((current / total) * 100)
    self.progressbar.SetProgress(percentage, message)
