from Utils.LogUtils import ErrorTypes
import psycopg2
from psycopg2 import OperationalError, sql
from Utils.ServerResponse import ServerResponse, ServerResponseObject


ORIGINAL_FILE_PATH_COLUMN_NAME = 'ORIGINAL_FILE_PATH'
SUMMARIZED_FILE_PATH_COLUMN_NAME = 'SUMMARIZED_FILE_PATH'


# if not success:
#   # If sql query fails for some reason, PostgreSQL aborts the transaction. If you don’t call conn.rollback(), every subsequent query fails as well.
#   self.connection.rollback()
class PostgresServerResponse(ServerResponse):
  def __init__(self, conn, rootFolder: str, logBaseName: str):
    self.conn = conn
    super().__init__(rootFolder, logBaseName)

  def GenerateServerResponse(  # type: ignore
    self,
    currentResponse: ServerResponseObject,
    className: str = '',
    errorType: ErrorTypes = ErrorTypes.Ok,
    generateLog=True,
    response: str = '',
  ):
    if not currentResponse.Success:
      self.conn.rollback()  # undo what we tried to do before we send the return.
    else:
      self.conn.commit()
    return super().GenerateServerResponse(
      currentResponse,
      className,
      errorType,
      generateLog,
    )


class PostgresManager:
  def __init__(
    self,
    username='test_username',
    password='test_password',
    address='localhost',
    port='5432',
    databaseName='test_db',
  ) -> None:
    self.username = username
    self.password = password
    self.address = address
    self.port = port

    # Connection to the database
    self.conn = psycopg2.connect(
      host=address,
      port=port,
      database=databaseName,
      user=username,
      password=password,
    )

    # Logger
    self.serverResponseUtil = PostgresServerResponse(
      self.conn, 'Postgres', 'postgres_log'
    )

  # --- Table creation ---
  def CreateTable(self, table_name: str, columns: dict) -> ServerResponseObject:
    """
    Create a table with given name and columns.

    Args:
        conn: psycopg2 connection object
        table_name (str): Name of the table to create
        columns (dict): Dictionary of {column_name: column_type}, e.g. {"id": "SERIAL PRIMARY KEY", "name": "TEXT", "age": "INT"}
    """
    currentResponse = ServerResponseObject()
    try:
      with self.conn.cursor() as cur:
        # Build column definitions safely
        col_defs = [
          sql.SQL('{} {}').format(sql.Identifier(col), sql.SQL(col_type))
          for col, col_type in columns.items()
        ]

        # Construct full CREATE TABLE statement
        query = sql.SQL('CREATE TABLE {table} ({fields});').format(
          table=sql.Identifier(table_name), fields=sql.SQL(', ').join(col_defs)
        )
        cur.execute(query)
        currentResponse.Success = True
        currentResponse.Message = (
          f'Table {table_name} created with columns {list(columns.keys())}'
        )
        return self.serverResponseUtil.GenerateServerResponse(currentResponse)
    except psycopg2.Error as e:
      currentResponse.Success = False
      currentResponse.Message = f'{e}'
      currentResponse.Finished = True
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        errorType=ErrorTypes.Error,
        className=__class__.__name__,
      )

  # --- Table Management ---
  def InsertIntoTable(self, tableName: str, data: dict) -> ServerResponseObject:
    """
    Insert a row into the specified table.

    Args:
        table_name (str): Name of the table
        data (dict): Dictionary of {column_name: value} to insert
    """
    currentResponse = ServerResponseObject()
    currentResponse.Success = False
    currentResponse.Message = 'Table does not exist'
    currentResponse.Finished = True
    if not self.TableExists(tableName).Success:
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        errorType=ErrorTypes.Error,
        className=__class__.__name__,
      )

    try:
      with self.conn.cursor() as cur:
        # Build columns and placeholders
        columns = [sql.Identifier(col) for col in data.keys()]
        values = [sql.Placeholder() for _ in data.values()]

        # Construct INSERT query
        query = sql.SQL(
          'INSERT INTO {table} ({fields}) VALUES ({vals}) RETURNING *;'
        ).format(
          table=sql.Identifier(tableName),
          fields=sql.SQL(', ').join(columns),
          vals=sql.SQL(', ').join(values),
        )

        cur.execute(query, tuple(data.values()))
        insertedRow = cur.fetchone()
        currentResponse.Success = True
        currentResponse.Message = (
          f'Inserted row into {tableName}: {insertedRow}'
        )
        currentResponse.Data = {'insertedRow': insertedRow}
        return self.serverResponseUtil.GenerateServerResponse(currentResponse)

    except psycopg2.Error as e:
      currentResponse.Success = False
      currentResponse.Message = f'{e}'
      currentResponse.Data = data
      currentResponse.Finished = True
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        errorType=ErrorTypes.Error,
        className=__class__.__name__,
      )

  def DeleteEntry(
    self, tableName: str, column: str, value
  ) -> ServerResponseObject:
    """
    Delete an entry from a table based on a WHERE condition.

    Args:
        table_name (str): Table to delete from
        where_column (str): Column to filter on
        value: Value for the WHERE condition
    """
    currentResponse = ServerResponseObject()
    try:
      with self.conn.cursor() as cur:
        query = sql.SQL('DELETE FROM {table} WHERE {col} = %s;').format(
          table=sql.Identifier(tableName), col=sql.Identifier(column)
        )
        cur.execute(query, (value,))
        self.conn.commit()

        if cur.rowcount > 0:
          currentResponse.Success = True
          currentResponse.Message = f'Deleted {cur.rowcount} row(s) from {tableName} where {column} ={value}'
        else:
          currentResponse.Success = False
          currentResponse.Message = (
            f'No matching entry found in {tableName} where {column} ={value}'
          )
          currentResponse.Finished = True
        return self.serverResponseUtil.GenerateServerResponse(currentResponse)

    except psycopg2.Error as e:
      currentResponse.Success = False
      currentResponse.Message = f'{e}'
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        errorType=ErrorTypes.Error,
        className=__class__.__name__,
      )

  def GetAllEntries(self, tableName) -> ServerResponseObject:
    """
    Fetch all rows from a given table.

    Args:
        tableName (str): Name of the table to query.

    Returns:
        Returns an object with a list of tuples containing the table rows.
    """
    currentResponse = ServerResponseObject()
    try:
      with self.conn.cursor() as cur:
        query = sql.SQL('SELECT * FROM {table};').format(
          table=sql.Identifier(tableName)
        )
        cur.execute(query)
        rows = cur.fetchall()
      currentResponse.Success = True
      currentResponse.Message = 'success'
      currentResponse.Data = {'entries': rows}
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        generateLog=False,
      )
    except Exception as e:
      print(f"Unexpected error while fetching entries from '{tableName}': {e}")
      currentResponse.Success = False
      currentResponse.Message = f'{e}'
      currentResponse.Data = {'entries': []}
      currentResponse.Finished = True
      return self.serverResponseUtil.GenerateServerResponse(currentResponse)

  def GetEntryByID(self, tableName: str, rowID: int) -> ServerResponseObject:
    """
    Fetch entry from a table by its 'id'.

    Args:
        tableName (str): Name of the table
        rowID (int): ID of the row to retrieve

    Returns:
        Returns an object with the table row that mach the given id.
    """
    currentResponse = ServerResponseObject()
    extraData = {'entries': {}}
    currentResponse.Data = extraData
    try:
      with self.conn.cursor() as cur:
        column = 'id'
        query = sql.SQL('SELECT * FROM {table} WHERE {col} = %s;').format(
          table=sql.Identifier(tableName), col=sql.Identifier(column)
        )
        cur.execute(query, (rowID,))
        self.conn.commit()
        row = cur.fetchone()

        if row is None:
          currentResponse.Message = (
            f'No entry found in {tableName} with id={rowID}'
          )
          currentResponse.Finished = True
          return self.serverResponseUtil.GenerateServerResponse(currentResponse)
        # Ensure description is available
        if cur.description is None:
          currentResponse.Message = (
            f'No column found in results set for table: {tableName}'
          )
          return self.serverResponseUtil.GenerateServerResponse(currentResponse)

        colNames = [desc[0] for desc in cur.description]
        result = dict(zip(colNames, row))
        if cur.rowcount > 0:
          currentResponse.Success = True
          currentResponse.Message = f'found {cur.rowcount} row(s) from {tableName} where {column}={rowID}'
          currentResponse.Data['entries'] = result
          return self.serverResponseUtil.GenerateServerResponse(currentResponse)
        else:
          currentResponse.Message = (
            f"No matching entry found in '{tableName}' where {column}={rowID}"
          )
          currentResponse.Finished = True
          return self.serverResponseUtil.GenerateServerResponse(currentResponse)
    except psycopg2.Error as e:
      currentResponse.Message = f'ERROR::GetEntryByID:: {e}'
      return self.serverResponseUtil.GenerateServerResponse(currentResponse)

  # --- Table deletion ---
  def PurgeTable(
    self, tableName: str, ifExists: bool = True
  ) -> ServerResponseObject:
    """
    Drop a table with he given name.
    Returns true if table was dropped successfully

    Args:
      tableName (str): Name of the table to create
      ifExists (bool): If True, use 'IF EXISTS' so it does not raise any error
    """
    self.serverResponseUtil.GenerateLogMessage(
      f'Dropping table: {tableName}...'
    )
    ifExists = self.TableExists(tableName).Success
    currentResponse = ServerResponseObject()
    try:
      with self.conn.cursor() as cur:
        query = sql.SQL('DROP TABLE {exists} {table};').format(
          exists=sql.SQL('IF EXISTS') if ifExists else sql.SQL(''),
          table=sql.Identifier(tableName),
        )
        cur.execute(query)
        currentResponse.Success = True
        currentResponse.Message = (
          f"Table '{tableName}' dropped (if existed: {ifExists})."
        )
        return self.serverResponseUtil.GenerateServerResponse(currentResponse)
    except OperationalError as e:
      currentResponse.Message = f'{e}'
      currentResponse.Finished = True
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        errorType=ErrorTypes.Error,
        className=__class__.__name__,
      )
    except Exception as e:
      currentResponse.Message = f'{e}'
      currentResponse.Finished = True
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        errorType=ErrorTypes.Error,
        className=__class__.__name__,
      )

  # --- Table Utils ---
  def TableExists(self, tableName: str):
    currentResponse = ServerResponseObject()
    try:
      with self.conn.cursor() as cur:
        cur.execute(
          'SELECT 1 FROM information_schema.tables WHERE table_name=%s',
          (tableName,),
        )
        currentResponse.Success = bool(cur.rowcount)

        return self.serverResponseUtil.GenerateServerResponse(
          currentResponse, generateLog=False
        )
    except psycopg2.Error as e:
      currentResponse.Message = f'{e}'
      currentResponse.Finished = True
      return self.serverResponseUtil.GenerateServerResponse(
        currentResponse,
        errorType=ErrorTypes.Error,
        className=__class__.__name__,
      )
