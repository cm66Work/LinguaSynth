import os
import requests
import concurrent.futures


class FileUploader:
  """Handles uploading TXT files to the server."""

  def __init__(self, directory, server_address, category, progress_callback=None):
    self.directory = directory
    self.server_address = server_address
    self.category = category
    self.progress_callback = progress_callback

  def upload_single_file(self, filepath):
    """Upload a single file and return (filename, status)."""
    try:
      with open(filepath, 'rb') as f:
        files = {'file': (os.path.basename(filepath), f, 'text/plain')}
        response = requests.post(
          f'{self.server_address}/upload-document/?documentCategory={self.category}',
          files=files,
        )
        return os.path.basename(filepath), response.status_code
    except Exception as e:
      return os.path.basename(filepath), str(e)

  def upload_all(self, max_workers=5):
    """Upload all .txt files in the directory concurrently."""
    txt_files = [f for f in os.listdir(self.directory) if f.endswith('.txt')]

    uploaded, failed = [], []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
      futures = [
        executor.submit(
          self.upload_single_file,
          os.path.join(self.directory, file),
        )
        for file in txt_files
      ]

      for future in concurrent.futures.as_completed(futures):
        filename, status = future.result()
        if status == 200:
          uploaded.append(filename)
        else:
          failed.append((filename, status))

        # Notify GUI about progress
        if self.progress_callback:
          self.progress_callback()

    return uploaded, failed
