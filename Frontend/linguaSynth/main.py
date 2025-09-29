import os
import tkinter as tk
from tkinter import filedialog, messagebox
import requests


def browse_directory():
  directory = filedialog.askdirectory()
  if directory:
    dir_entry.delete(0, tk.END)
    dir_entry.insert(0, directory)


def upload_files():
  directory = dir_entry.get().strip()
  server_address = server_entry.get().strip()

  if not directory or not server_address:
    messagebox.showerror('Error', 'Both fields are required!')
    return

  if not os.path.isdir(directory):
    messagebox.showerror('Error', f'{directory} is not a valid directory')
    return

  txt_files = [f for f in os.listdir(directory) if f.endswith('.txt')]
  if not txt_files:
    messagebox.showinfo('Info', 'No .txt files found in directory.')
    return

  uploaded = []
  failed = []

  for file in txt_files:
    filepath = os.path.join(directory, file)
    try:
      with open(filepath, 'rb') as f:
        files = {'file': (file, f, 'text/plain')}
        response = requests.post(f'{server_address}/upload', files=files)
        if response.status_code == 200:
          uploaded.append(file)
        else:
          failed.append((file, response.status_code))
    except Exception as e:
      failed.append((file, str(e)))

  result_msg = (
    f'Uploaded: {uploaded}\nFailed: {failed}'
    if failed
    else f'All files uploaded successfully: {uploaded}'
  )
  messagebox.showinfo('Upload Result', result_msg)


# GUI setup
root = tk.Tk()
root.title('TXT File Uploader')

tk.Label(root, text='File Directory:').grid(row=0, column=0, sticky='w', padx=5, pady=5)
dir_entry = tk.Entry(root, width=50)
dir_entry.grid(row=0, column=1, padx=5, pady=5)
tk.Button(root, text='Browse', command=browse_directory).grid(
  row=0, column=2, padx=5, pady=5
)

tk.Label(root, text='Server Address:').grid(row=1, column=0, sticky='w', padx=5, pady=5)
server_entry = tk.Entry(root, width=50)
server_entry.grid(row=1, column=1, padx=5, pady=5)

tk.Button(root, text='Upload Files', command=upload_files).grid(
  row=2, column=0, columnspan=3, pady=10
)

root.mainloop()
