import tkinter as tk
from tkinter import filedialog, Frame

from Utils.CustomTK import TextProgressBar
from Panels.FileUploadPanel import FileUploadPanel
from Panels.SchemaGenerationPanel import SchemaGenerationPanel
from Panels.ProcessNewUploadedDocumentsPanel import ProcessNewUploadDocumentsPanel
from Panels.SchemaUploadPanel import SchemaUploadPanel
from Panels.DocumentIndexingPanel import DocumentIndexingPanel


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
    tk.Button(
      buttonFrame, text='Index documents', command=self.StartIndexingDocuments
    ).pack(side='bottom')
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
    generationButtonFrame = Frame(self.schemaGeneration)
    generationButtonFrame.pack(anchor='n')
    tk.Button(generationButtonFrame, text='Generate', command=self.GenerateSchema).pack(
      side='left'
    )
    tk.Button(generationButtonFrame, text='Upload', command=self.UploadSchema).pack(
      side='right'
    )

    self.root.update_idletasks()
    self.generatedSchema = tk.Entry(
      self.schemaGeneration, width=self.schemaGeneration.winfo_width() - 2
    )
    self.generatedSchema.pack()
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
    self.processNewDocumentsPanel = ProcessNewUploadDocumentsPanel(
      serverAddress=self.serverAddress,
      categoryName=self.schemaCategoryName,
      progressbar=self.progressbar,
    )
    self.processNewDocumentsPanel.ProcessNewUploadedDocuments()

  def GenerateSchema(self):
    self.schemaGenerationPanel = SchemaGenerationPanel(
      sampleSize=self.sampleSize,
      resolution=self.resolution,
      serverAddress=self.serverAddress,
      categoryName=self.schemaCategoryName,
      generatedSchema=self.generatedSchema,
      progressbar=self.progressbar,
    )
    self.schemaGenerationPanel.GenerateSchema()

  def UploadSchema(self):
    self.schemaUploadPanel = SchemaUploadPanel(
      serverAddress=self.serverAddress,
      categoryName=self.schemaCategoryName,
      schemaJsonString=self.generatedSchema,
      progressbar=self.progressbar,
    )
    self.schemaUploadPanel.UploadSchema()

  def StartIndexingDocuments(self):
    self.documentIndexingPanel = DocumentIndexingPanel(
      serverAddress=self.serverAddress,
      categoryName=self.schemaCategoryName,
      progressbar=self.progressbar,
    )
    self.documentIndexingPanel.StartIndexingDocuments()

  def SendQuestion(self):
    pass


if __name__ == '__main__':
  root = tk.Tk()
  root.title('LinguaSynth Testing Frontend')
  root.configure(bg='black')

  myWindow = TKWindow(root)
  myWindow.start()
