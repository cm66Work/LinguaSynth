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

  def GenerateServerResponse(
    self,
    success: bool,
    message: str,
    extraData: dict = {},
    generateLog=True,
  ):
    if not success:
      self.conn.rollback()  # undo what we tried to do before we send the return.
    else:
      self.conn.commit()
    return super().GenerateServerResponse(success, message, extraData, generateLog)


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
        return self.serverResponseUtil.GenerateServerResponse(
          success=True,
          message=f"Table '{table_name}' created with columns {list(columns.keys())}",
        )
    except psycopg2.Error as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False, message=f'ERROR::PostgresManager::CreateTable:: {e}'
      )

  # --- Table Management ---
  def InsertIntoTable(self, tableName: str, data: dict) -> ServerResponseObject:
    """
    Insert a row into the specified table.

    Args:
        table_name (str): Name of the table
        data (dict): Dictionary of {column_name: value} to insert
    """
    if not self.TableExists(tableName).Success:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False,
        message='ERROR::InsertIntoTable:: Table does not exist',
        extraData=data,
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
        inserted_row = cur.fetchone()
        return self.serverResponseUtil.GenerateServerResponse(
          success=True,
          message=f"Inserted row into '{tableName}': {inserted_row}",
          extraData={'insertedRow': inserted_row},
        )

    except psycopg2.Error as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False, message=f'ERROR::InsertIntoTable:: {e}', extraData=data
      )

  def DeleteEntry(self, tableName: str, column: str, value) -> ServerResponseObject:
    """
    Delete an entry from a table based on a WHERE condition.

    Args:
        table_name (str): Table to delete from
        where_column (str): Column to filter on
        value: Value for the WHERE condition
    """
    try:
      with self.conn.cursor() as cur:
        query = sql.SQL('DELETE FROM {table} WHERE {col} = %s;').format(
          table=sql.Identifier(tableName), col=sql.Identifier(column)
        )
        cur.execute(query, (value,))
        self.conn.commit()

        if cur.rowcount > 0:
          return self.serverResponseUtil.GenerateServerResponse(
            success=True,
            message=f"Deleted {cur.rowcount} row(s) from '{tableName}' where {column}={value}",
          )
        else:
          return self.serverResponseUtil.GenerateServerResponse(
            success=False,
            message=f"No matching entry found in '{tableName}' where {column}={value}",
          )
    except psycopg2.Error as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False, message=f'ERROR::DeleteEntry:: {e}'
      )

  def GetAllEntries(self, tableName) -> ServerResponseObject:
    """
    Fetch all rows from a given table.

    Args:
        tableName (str): Name of the table to query.

    Returns:
        Returns an object with a list of tuples containing the table rows.
    """
    try:
      with self.conn.cursor() as cur:
        query = sql.SQL('SELECT * FROM {table};').format(table=sql.Identifier(tableName))
        cur.execute(query)
        rows = cur.fetchall()
      return self.serverResponseUtil.GenerateServerResponse(
        success=True, message='success', extraData={'entries': rows}, generateLog=False
      )
    except Exception as e:
      print(f"Unexpected error while fetching entries from '{tableName}': {e}")
      return self.serverResponseUtil.GenerateServerResponse(
        success=False, message=f'ERROR::GetAllEntries:: {e}', extraData={'entries': []}
      )

  def GetEntryByID(self, tableName: str, rowID: int) -> ServerResponseObject:
    """
    Fetch entry from a table by its 'id'.

    Args:
        tableName (str): Name of the table
        rowID (int): ID of the row to retrieve

    Returns:
        Returns an object with the table row that mach the given id.
    """
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
          return self.serverResponseUtil.GenerateServerResponse(
            success=False,
            message=f"No entry found in '{tableName}' with id={rowID}",
            extraData={'entries': {}},
          )
        # Ensure description is available
        if cur.description is None:
          print()
          return self.serverResponseUtil.GenerateServerResponse(
            success=False,
            message=f'No columns found in result set for table: {tableName}',
            extraData={'entries': {}},
          )
        colNames = [desc[0] for desc in cur.description]
        result = dict(zip(colNames, row))
        if cur.rowcount > 0:
          return self.serverResponseUtil.GenerateServerResponse(
            success=True,
            message=f"Found {cur.rowcount} row(s) from '{tableName}' where {column}={rowID}",
            extraData={'entries': result},
          )
        else:
          return self.serverResponseUtil.GenerateServerResponse(
            success=False,
            message=f"No matching entry found in '{tableName}' where {column}={rowID}",
            extraData={'entries': []},
          )
    except psycopg2.Error as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False, message=f'ERROR::GetEntryByID:: {e}', extraData={'entries': {}}
      )

  # --- Table deletion ---
  def PurgeTable(self, tableName: str, ifExists: bool = True) -> ServerResponseObject:
    """
    Drop a table with he given name.
    Returns true if table was dropped successfully

    Args:
      tableName (str): Name of the table to create
      ifExists (bool): If True, use 'IF EXISTS' so it does not raise any error
    """
    self.serverResponseUtil.GenerateLogMessage(f'Dropping table: {tableName}...')
    ifExists = self.TableExists(tableName).Success
    try:
      with self.conn.cursor() as cur:
        query = sql.SQL('DROP TABLE {exists} {table};').format(
          exists=sql.SQL('IF EXISTS') if ifExists else sql.SQL(''),
          table=sql.Identifier(tableName),
        )
        cur.execute(query)
        return self.serverResponseUtil.GenerateServerResponse(
          success=True, message=f"Table '{tableName}' dropped (if existed: {ifExists})."
        )
    except OperationalError as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False, message=f'ERROR::PostgresManager.PurgeTable:: {e}'
      )
    except Exception as e:
      return self.serverResponseUtil.GenerateServerResponse(
        success=False, message=f'ERROR::PostgresManager.PurgeTable:: {e}'
      )

  # --- Table Utils ---
  def TableExists(self, tableName: str):
    try:
      with self.conn.cursor() as cur:
        cur.execute(
          'SELECT 1 FROM information_schema.tables WHERE table_name=%s',
          (tableName,),
        )
        return self.serverResponseUtil.GenerateServerResponse(
          success=bool(cur.rowcount), message='', generateLog=False
        )
    except psycopg2.Error as e:
      return self.serverResponseUtil.GenerateServerResponse(success=False, message=f'{e}')
