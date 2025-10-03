import tkinter as tk
from tkinter import filedialog, Frame

from Utils.CustomTK import TextProgressBar
from Panels.FileUploadPanel import FileUploadPanel
from Panels.SchemaGenerationPanel import SchemaGenerationPanel


class TKWindow:
  def __init__(self, root: tk.Tk, width: int = 1200, height: int = 600):
    self.root = root
    self.root.geometry(f'{width}x{height}')
    # Create the 3/4 window
    self.root.grid_columnconfigure(0, weight=1, uniform='split')
    self.root.grid_columnconfigure(1, weight=3, uniform='split')
    self.root.grid_rowconfigure(0, weight=1)

    # left side 1/4 frame: Frame 1
    self.leftFrame = Frame(self.root, bg='lightblue')
    self.leftFrame.grid(row=0, column=0, sticky='nesw', padx=1)
    self.leftFrame.grid_columnconfigure(0, weight=1)
    self.leftFrame.grid_rowconfigure(0, weight=1, uniform='split')
    self.leftFrame.grid_rowconfigure(1, weight=2, uniform='split')
    self.leftFrame.grid_rowconfigure(2, weight=2, uniform='split')
    # file path: frame 1.1
    self.filepathFrame = Frame(self.leftFrame, bg='lightgray', padx=10, pady=10)
    self.filepathFrame.grid(row=0, column=0, sticky='nsew')
    # schema category: Frame 1.2
    self.schemaCategory = Frame(self.leftFrame, bg='lightgray', padx=10, pady=10)
    self.schemaCategory.grid(row=1, column=0, sticky='nsew')
    # Schema generation: Frame 1.3
    self.schemaGeneration = Frame(self.leftFrame, bg='lightgray', padx=10, pady=10)
    self.schemaGeneration.grid(row=2, column=0, sticky='nsew')

    # right side 3/4 frame: Frame 2
    self.rightFrame = Frame(self.root, bg='lightgreen')
    self.rightFrame.grid(row=0, column=1, sticky='nesw', padx=1)
    self.rightFrame.grid_columnconfigure(0, weight=1)
    self.rightFrame.grid_rowconfigure(0, weight=1, uniform='split')
    self.rightFrame.grid_rowconfigure(1, weight=4, uniform='split')
    self.rightFrame.grid_rowconfigure(2, weight=1, uniform='split')
    # server address: Frame 2.1
    self.serverAddressFrame = Frame(self.rightFrame, bg='lightgray', padx=10, pady=10)
    self.serverAddressFrame.grid(row=0, column=0, sticky='nsew')
    # AI chat: Frame 2.2
    self.chatFrame = Frame(self.rightFrame, bg='lightgray', padx=10, pady=10)
    self.chatFrame.grid(row=1, column=0, sticky='nsew')
    self.chatFrame.grid_columnconfigure(0, weight=1)
    self.chatFrame.grid_rowconfigure(0, weight=4, uniform='split')
    self.chatFrame.grid_rowconfigure(1, weight=1, uniform='split')
    # Progressbar: Frame 2.3
    self.progressbarFrame = Frame(self.rightFrame, bg='lightgray', padx=10, pady=10)
    self.progressbarFrame.grid(row=2, column=0, sticky='nsew')

    # region Filepath
    tk.Label(self.filepathFrame, text='File Directory:').pack(anchor='nw')
    self.fileDirectory = tk.Entry(self.filepathFrame, width=50)
    self.fileDirectory.pack(anchor='nw')
    tk.Button(self.filepathFrame, text='Browse', command=self.BrowsDirectory).pack()
    # endregion

    # region category
    tk.Label(self.schemaCategory, text='Schema category').pack(anchor='n')
    tk.Label(self.schemaCategory, text='Name:').pack(anchor='w', padx=1)
    self.schemaCategoryName = tk.Entry(self.schemaCategory, width=25)
    self.schemaCategoryName.pack(anchor='w')
    tk.Label(self.schemaCategory, text='Summarization\nPasses:').pack(anchor='w', padx=1)
    self.summarizationPasses = tk.Entry(self.schemaCategory, width=25)
    self.summarizationPasses.pack(anchor='w')
    tk.Label(self.schemaCategory, text='Options').pack(anchor='n', padx=1)
    buttonFrame = Frame(self.schemaCategory)
    buttonFrame.pack(anchor='n')
    tk.Button(buttonFrame, text='Upload files', command=self.UploadFiles).pack(
      side='left'
    )
    tk.Button(buttonFrame, text='Process documents', command=self.ProcessDocuments).pack(
      side='right'
    )
    # endregion

    # region schema generation
    tk.Label(self.schemaGeneration, text='Schema generation').pack(anchor='n')

    sampleSizeOptionFrame = Frame(self.schemaGeneration)
    sampleSizeOptionFrame.pack(anchor='n')
    tk.Label(sampleSizeOptionFrame, text='Sample size:').pack(side='left', padx=1)
    self.sampleSize = tk.Entry(sampleSizeOptionFrame, width=15)
    self.sampleSize.pack(side='right')

    resolutionOptionFrame = Frame(self.schemaGeneration)
    resolutionOptionFrame.pack(anchor='n')
    tk.Label(resolutionOptionFrame, text='Resolution:').pack(side='left', padx=1)
    self.resolution = tk.Entry(resolutionOptionFrame, width=15)
    self.resolution.pack(side='right')
    tk.Button(self.schemaGeneration, text='Generate', command=self.GenerateSchema).pack(
      anchor='n'
    )
    # endregion

    # region server address
    addressFrame = Frame(self.serverAddressFrame)
    addressFrame.pack(anchor='n')
    tk.Label(addressFrame, text='Address:').pack(side='left', padx=1)
    self.serverAddress = tk.Entry(addressFrame, width=60)
    self.serverAddress.pack(side='right')
    # endregion

    # region chat
    self.chatAIResponse = tk.Label(self.chatFrame, text='Hi!', bg='white')
    self.chatAIResponse.grid(row=0, column=0, sticky='nesw')

    userMessageFrame = Frame(self.chatFrame)
    userMessageFrame.grid(row=1, column=0, sticky='nesw')
    self.userQuestion = tk.Entry(userMessageFrame, width=100)
    self.userQuestion.pack(side='left')
    tk.Button(userMessageFrame, text='Send', command=self.SendQuestion).pack(side='right')
    # endregion

    # region progressbar
    # use before calling Frame.winfo_width()
    self.root.update_idletasks()
    self.progressbar = TextProgressBar(self.progressbarFrame, width=600, height=15)
    self.progressbar.grid(row=3, column=0)
    # endregion

    # regions Panels
    # endregion

  def start(self):
    self.root.mainloop()

  def BrowsDirectory(self):
    directory = filedialog.askdirectory()
    if directory:
      self.fileDirectory.delete(0, tk.END)
      self.fileDirectory.insert(0, directory)

  def UploadFiles(self):
    self.fileUploadPanel = FileUploadPanel(
      rootDirectory=self.fileDirectory,
      serverAddress=self.serverAddress,
      categoryName=self.schemaCategoryName,
      progressbar=self.progressbar,
    )
    self.fileUploadPanel.UploadFiles()

  def ProcessDocuments(self):
    pass

  def GenerateSchema(self):
    self.schemaGenerationPanel = SchemaGenerationPanel(
      sampleSize=self.sampleSize,
      resolution=self.resolution,
      serverAddress=self.serverAddress,
      categoryName=self.schemaCategoryName,
      progressbar=self.progressbar,
    )
    self.schemaGenerationPanel.GenerateSchema()

  def SendQuestion(self):
    pass


if __name__ == '__main__':
  root = tk.Tk()
  root.title('LinguaSynth Testing Frontend')
  root.configure(bg='black')

  myWindow = TKWindow(root)
  myWindow.start()


# # GUI setupV
# root = tk.Tk()
# root.title('LinguaSynth Testing Frontend')

# # Frames
# fileUploadFrame = tk.Frame(root)
# fileUploadFrame.grid(row=0, column=0, columnspan=3, pady=10)

# button_frame = tk.Frame(root)
# button_frame.grid(row=3, column=0, columnspan=3, pady=10)

# progressbar_frame = tk.Frame(root)
# progressbar_frame.grid(column=0, columnspan=3, pady=10)


# # Progress bar (hidden initially)
# progress = ttk.Progressbar(
#   progressbar_frame, orient='horizontal', mode='determinate', length=300
# )
# progress.grid(row=0, column=0, padx=10, pady=10)
# progressbar_label = tk.Label(progressbar_frame, text='Estimated time remaining: --:--')
# progressbar_label.grid(row=1, column=0, padx=10, pady=5)


# # region Processed new uploaded document
# def ProcessNewUploadedDocuments():
#   server_address = server_entry.get().strip()
#   category = category_entry.get().strip()

#   if not server_address or not category:
#     messagebox.showerror('Error', 'server address and category are required!')
#     return

#   # Show progress bar
#   progressbar_frame.grid(row=4, column=0, columnspan=3, pady=10)
#   progress['maximum'] = 100
#   progress['value'] = 0

#   def update_progress(value: int, max: int, startTime):
#     value += 1
#     progress['maximum'] = max
#     progress['value'] = value
#     root.update_idletasks()

#     # compute ETA
#     if value > 0:
#       elapsed = time.time() - startTime
#       rate = elapsed / value
#       remaining = rate * (max - value)

#       mins, secs = divmod(int(remaining), 60)

#       progressbar_label.config(
#         text=f'files processed: {value}/{max} | etr: {mins:02d}:{secs:02d}'
#       )
#     else:
#       progressbar_label.config(
#         text=f'files processed: {value}/{max} | etc: Calculating...'
#       )

#   processor = ProcessUploadedDocuments.ProcessUploadedDocuments(
#     server_address, category, update_progress
#   )
#   result, statusCode = processor.ProcessFiles(time.time())
#   # print('Final:', result, statusCode)

#   # Hide progress bar when done
#   progressbar_frame.grid_forget()

#   messagebox.showinfo('Upload Result', result)


# # --- GUI

# tk.Button(
#   button_frame, text='Process Documents', command=ProcessNewUploadedDocuments
# ).pack(side='right', padx=5)

# tk.Label(button_frame, text='Summarization Passes:').pack(side='left', padx=5)
# summarizationPasses = tk.Entry(button_frame, width=5)
# summarizationPasses.pack(side='left', padx=5)

# # endregion

# fileDirectory = tk.Frame(fileUploadFrame)
# fileDirectory.grid(row=0, column=0, columnspan=3, pady=5)
# tk.Label(fileDirectory, text='File Directory:').grid(
#   row=0, column=0, sticky='w', padx=0, pady=5
# )
# dir_entry = tk.Entry(fileDirectory, width=50)
# dir_entry.grid(row=0, column=1, padx=5, pady=5)
# tk.Button(fileDirectory, text='Browse', command=browse_directory).grid(
#   row=0, column=2, padx=5, pady=5
# )


# serverAddressFrame = tk.Frame(fileUploadFrame)
# serverAddressFrame.grid(row=1, column=0, columnspan=3, pady=5)
# tk.Label(serverAddressFrame, text='Server Address:').grid(
#   row=0, column=0, sticky='w', padx=5, pady=5
# )
# server_entry = tk.Entry(serverAddressFrame, width=15)
# server_entry.grid(row=0, column=1, padx=5, pady=5)
# tk.Label(serverAddressFrame, text='Document Category:').grid(
#   row=0, column=2, sticky='w', padx=5, pady=5
# )
# category_entry = tk.Entry(serverAddressFrame, width=15)
# category_entry.grid(row=0, column=3, padx=5, pady=5)


# schemaGenerationFrame = tk.Frame(root)
# schemaGenerationFrame.grid(row=5)
# tk.Label(schemaGenerationFrame, text='Schema Generation ------------').grid(
#   row=0, column=0, sticky='w'
# )

# schemaVariablesFrame = tk.Frame(schemaGenerationFrame)
# schemaVariablesFrame.grid(row=1, column=0)
# tk.Label(schemaVariablesFrame, text='Sample size:').grid(
#   row=0, column=0, sticky='w', padx=5, pady=5
# )
# schemaSampleSize = tk.Entry(schemaVariablesFrame, width=10)
# schemaSampleSize.grid(row=0, column=1)

# tk.Label(schemaVariablesFrame, text='Resolution:').grid(
#   row=1, column=0, sticky='w', padx=5, pady=5
# )
# schemaResolution = tk.Entry(schemaVariablesFrame, width=10)
# schemaResolution.grid(row=1, column=1)

# tk.Button(schemaGenerationFrame, text='Generate', command=GenerateSchema).grid(
#   row=1, column=1, padx=5, pady=5
# )

# # Progress bar (hidden initially)
# schemaProgressbarFrame = tk.Frame(schemaGenerationFrame)
# schemaProgressbarFrame.grid(row=0, column=1)

# documentProcessedProgressbar_label = tk.Label(
#   schemaProgressbarFrame, text='Estimated time remaining: --:--'
# )
# documentProcessedProgressbar_label.grid(row=0, column=0, padx=10, pady=5)
# documentProcessedProgress = ttk.Progressbar(
#   progressbar_frame, orient='horizontal', mode='determinate', length=300
# )
# documentProcessedProgress.grid(row=0, column=0, padx=10, pady=10)

# schemaProcessedProgressbar_label = tk.Label(
#   schemaProgressbarFrame, text='Estimated time remaining: --:--'
# )
# schemaProcessedProgressbar_label.grid(row=1, column=0, padx=10, pady=5)
# schemaProcessedProgress = ttk.Progressbar(
#   progressbar_frame, orient='horizontal', mode='determinate', length=300
# )
# schemaProcessedProgress.grid(row=1, column=0, padx=10, pady=10)

# root.mainloop()
