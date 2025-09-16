import datetime
import os


class LogUtil:
  def __init__(self, rootFolder, logBaseName):
    # self.logger = logging.getLogger(logBaseName)
    date = f'{datetime.datetime.now().strftime("%d")}'
    date += f'-{datetime.datetime.now().strftime("%m")}'
    date += f'-{datetime.datetime.now().strftime("%y")}'
    date += f'-{datetime.datetime.now().strftime("%H")}'
    # date += f'-{datetime.datetime.now().strftime("%M")}'
    # date += f'-{datetime.datetime.now().strftime("%S")}'
    date += '.txt'
    directory = f'{os.curdir}/Logs/{rootFolder}'
    os.makedirs(directory, exist_ok=True)
    # logging.basicConfig(filename=f'{directory}/{logBaseName}:{date}', level=logging.INFO)
    self.logFilePath = f'{directory}/{logBaseName}:{date}.txt'
    self.GenerateLogMessage(f'New {rootFolder} Log Started.................')

  def GenerateLogMessage(self, messageString):
    """
    Creates a log message in the current log file
    """
    # if os.path.exists(self.logFilePath):
    with open(self.logFilePath, 'a') as f:
      f.write(f'\n{messageString}')
    # self.logger.info(f'\n{messageString}')
