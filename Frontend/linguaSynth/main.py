import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from ButtonActions import UploadFile, ProcessUploadedDocuments

# GUI setup
root = tk.Tk()
root.title('TXT File Uploader')

# Frames
fileUploadFrame = tk.Frame(root)
fileUploadFrame.grid(row=0, column=0, columnspan=3, pady=10)

button_frame = tk.Frame(root)
button_frame.grid(row=3, column=0, columnspan=3, pady=10)

progressbar_frame = tk.Frame(root)
progressbar_frame.grid(column=0, columnspan=3, pady=10)


# Progress bar (hidden initially)
progress = ttk.Progressbar(
  progressbar_frame, orient='horizontal', mode='determinate', length=300
)
progress.grid(row=0, column=0, padx=10, pady=10)
progressbar_label = tk.Label(progressbar_frame, text='Estimated time remaining: --:--')
progressbar_label.grid(row=1, column=0, padx=10, pady=5)


def browse_directory():
  directory = filedialog.askdirectory()
  if directory:
    dir_entry.delete(0, tk.END)
    dir_entry.insert(0, directory)


# region Upload files
def upload_files():
  # Run upload in a background thread so GUI stays responsive
  threading.Thread(target=_upload_files_thread, daemon=True).start()


def _upload_files_thread():
  directory = dir_entry.get().strip()
  server_address = server_entry.get().strip()
  category = category_entry.get().strip()

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
  progressbar_frame.grid(row=4, column=0, columnspan=3, pady=10)
  progress['maximum'] = len(txt_files)
  progress['value'] = 0

  def update_progress():
    progress.step(1)
    root.update_idletasks()

  # Use the uploader class
  uploader = UploadFile.FileUploader(
    directory=directory,
    server_address=server_address,
    category=category,
    progress_callback=update_progress,
  )
  uploaded, failed = uploader.upload_all()

  # Hide progress bar
  progressbar_frame.grid_forget()

  result_msg = (
    f'Uploaded: {uploaded}\nFailed: {failed}'
    if failed
    else f'All files uploaded successfully: {uploaded}'
  )
  messagebox.showinfo('Upload Result', result_msg)


# GUI

tk.Button(button_frame, text='Upload Files', command=upload_files).pack(
  side='left', padx=5
)
# endregion


# region Processed new uploaded document
def ProcessNewUploadedDocuments():
  server_address = server_entry.get().strip()
  category = category_entry.get().strip()

  if not server_address or not category:
    messagebox.showerror('Error', 'server address and category are required!')
    return

  # Show progress bar
  progressbar_frame.grid(row=4, column=0, columnspan=3, pady=10)
  progress['maximum'] = 100
  progress['value'] = 0

  def update_progress(value: int, max: int, startTime):
    value += 1
    progress['maximum'] = max
    progress['value'] = value
    root.update_idletasks()

    # compute ETA
    if value > 0:
      elapsed = time.time() - startTime
      rate = elapsed / value
      remaining = rate * (max - value)

      mins, secs = divmod(int(remaining), 60)

      progressbar_label.config(
        text=f'files processed: {value}/{max} | etr: {mins:02d}:{secs:02d}'
      )
    else:
      progressbar_label.config(
        text=f'files processed: {value}/{max} | etc: Calculating...'
      )

  processor = ProcessUploadedDocuments.ProcessUploadedDocuments(
    server_address, category, update_progress
  )
  result, statusCode = processor.ProcessFiles(time.time())
  # print('Final:', result, statusCode)

  # Hide progress bar when done
  progressbar_frame.grid_forget()

  messagebox.showinfo('Upload Result', result)


# --- GUI

tk.Button(
  button_frame, text='Process Documents', command=ProcessNewUploadedDocuments
).pack(side='right', padx=5)

tk.Label(button_frame, text='Summarization Passes:').pack(side='left', padx=5)
summarizationPasses = tk.Entry(button_frame, width=5)
summarizationPasses.pack(side='left', padx=5)

# endregion

fileDirectory = tk.Frame(fileUploadFrame)
fileDirectory.grid(row=0, column=0, columnspan=3, pady=5)
tk.Label(fileDirectory, text='File Directory:').grid(
  row=0, column=0, sticky='w', padx=0, pady=5
)
dir_entry = tk.Entry(fileDirectory, width=50)
dir_entry.grid(row=0, column=1, padx=5, pady=5)
tk.Button(fileDirectory, text='Browse', command=browse_directory).grid(
  row=0, column=2, padx=5, pady=5
)


serverAddressFrame = tk.Frame(fileUploadFrame)
serverAddressFrame.grid(row=1, column=0, columnspan=3, pady=5)
tk.Label(serverAddressFrame, text='Server Address:').grid(
  row=0, column=0, sticky='w', padx=5, pady=5
)
server_entry = tk.Entry(serverAddressFrame, width=15)
server_entry.grid(row=0, column=1, padx=5, pady=5)
tk.Label(serverAddressFrame, text='Document Category:').grid(
  row=0, column=2, sticky='w', padx=5, pady=5
)
category_entry = tk.Entry(serverAddressFrame, width=15)
category_entry.grid(row=0, column=3, padx=5, pady=5)


# region Schema generation


schemaGenerationFrame = tk.Frame(root)
schemaGenerationFrame.grid(row=5)
tk.Label(schemaGenerationFrame, text='Schema Generation ------------').grid(
  row=0, column=0, sticky='w'
)

tk.Label(schemaGenerationFrame, text='Number of random files to use:').grid(
  row=1, column=0, sticky='w', padx=5, pady=5
)
schemaNumberRandomFilesToUse = tk.Entry(schemaGenerationFrame, width=5)
schemaNumberRandomFilesToUse.grid(row=1, column=2, padx=5, pady=5)
tk.Button(schemaGenerationFrame, text='Generate', command=browse_directory).grid(
  row=1, column=3, padx=5, pady=5
)


root.mainloop()
