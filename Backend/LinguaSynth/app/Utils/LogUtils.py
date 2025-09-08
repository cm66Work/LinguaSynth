import datetime
import os
import logging


class LogUtil:
  def __init__(self, rootFolder, logBaseName):
    self.logger = logging.getLogger(__name__)
    date = f'{datetime.datetime.now().strftime("%d")}'
    date += f'-{datetime.datetime.now().strftime("%m")}'
    date += f'-{datetime.datetime.now().strftime("%y")}'
    date += f'-{datetime.datetime.now().strftime("%H")}'
    date += f'-{datetime.datetime.now().strftime("%M")}'
    date += f'-{datetime.datetime.now().strftime("%S")}'
    date += '.txt'
    directory = f'{os.curdir}/Logs/{rootFolder}'
    os.makedirs(directory, exist_ok=True)
    logging.basicConfig(filename=f'{directory}/{logBaseName}:{date}', level=logging.INFO)

  def GenerateLogMessage(self, messageString):
    """
    Creates a log message in the current log file
    """
    self.logger.info('\nmessageString')
