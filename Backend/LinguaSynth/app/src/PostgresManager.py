import psycopg2
from psycopg2 import sql
from Utils.LogUtils import LogUtil  # type: ignore

ORIGINAL_FILE_PATH_COLUMN_NAME = 'ORIGINAL_FILE_PATH'
SUMMARIZED_FILE_PATH_COLUMN_NAME = 'SUMMARIZED_FILE_PATH'


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

    # Logger
    self.log = LogUtil('Postgres', 'postgres_log')

    # Connection to the database
    self.conn = psycopg2.connect(
      host=address,
      port=port,
      database=databaseName,
      user=username,
      password=password,
    )

  # --- Table creation ---
  def CreateTable(self, table_name: str, columns: dict):
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
        return self.__GenerateResponse(
          True,
          f"Table '{table_name}' created with columns {list(columns.keys())}",
        )
    except psycopg2.Error as e:
      return self.__GenerateResponse(False, f'ERROR::PostgresManager::CreateTable:: {e}')

  # --- Table Management ---
  def InsertIntoTable(self, tableName: str, data: dict):
    """
    Insert a row into the specified table.

    Args:
        table_name (str): Name of the table
        data (dict): Dictionary of {column_name: value} to insert
    """
    if not self.TableExists(tableName)['success']:
      return self.__GenerateResponse(
        False, 'ERROR::InsertIntoTable:: Table does not exist', data
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
        return self.__GenerateResponse(
          True,
          f"Inserted row into '{tableName}': {inserted_row}",
          {'insertedRow': inserted_row},
        )

    except psycopg2.Error as e:
      return self.__GenerateResponse(False, f'ERROR::InsertIntoTable:: {e}', data)

  def DeleteEntry(self, tableName: str, column: str, value):
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
          return self.__GenerateResponse(
            True,
            f"Deleted {cur.rowcount} row(s) from '{tableName}' where {column}={value}",
          )
        else:
          return self.__GenerateResponse(
            False,
            f"No matching entry found in '{tableName}' where {column}={value}",
          )
    except psycopg2.Error as e:
      return self.__GenerateResponse(False, f'ERROR::DeleteEntry:: {e}')

  def GetAllEntries(self, tableName):
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
      return self.__GenerateResponse(True, 'success', {'entries': rows})
    except Exception as e:
      print(f"Unexpected error while fetching entries from '{tableName}': {e}")
      return self.__GenerateResponse(
        False, f'ERROR::GetAllEntries:: {e}', {'entries': []}
      )

  def GetEntryByID(self, tableName: str, rowID: int):
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
          return self.__GenerateResponse(
            False,
            f"No entry found in '{tableName}' with id={rowID}",
            {'entries': {}},
          )
        # Ensure description is available
        if cur.description is None:
          print()
          return self.__GenerateResponse(
            False,
            f'No columns found in result set for table: {tableName}',
            {'entries': {}},
          )
        colNames = [desc[0] for desc in cur.description]
        result = dict(zip(colNames, row))
        if cur.rowcount > 0:
          return self.__GenerateResponse(
            True,
            f"Found {cur.rowcount} row(s) from '{tableName}' where {column}={rowID}",
            {'entries': result},
          )
        else:
          return self.__GenerateResponse(
            False,
            f"No matching entry found in '{tableName}' where {column}={rowID}",
            {'entries': []},
          )
    except psycopg2.Error as e:
      return self.__GenerateResponse(False, f'ERROR::GetEntryByID:: {e}', {'entries': {}})

  # --- Table deletion ---
  def PurgeTable(self, tableName: str, ifExists: bool = True):
    """
    Drop a table with he given name.
    Returns true if table was dropped successfully

    Args:
      tableName (str): Name of the table to create
      ifExists (bool): If True, use 'IF EXISTS' so it does not raise any error
    """
    self.log.GenerateLogMessage(f'Dropping table: {tableName}...')
    ifExists = self.TableExists(tableName)['success']
    try:
      with self.conn.cursor() as cur:
        query = sql.SQL('DROP TABLE {exists} {table};').format(
          exists=sql.SQL('IF EXISTS') if ifExists else sql.SQL(''),
          table=sql.Identifier(tableName),
        )
        cur.execute(query)
        return self.__GenerateResponse(
          True, f"Table '{tableName}' dropped (if existed: {ifExists})."
        )
    except Exception as e:
      return self.__GenerateResponse(False, f'ERROR::PurgeTable:: {e}')

  # --- Table Utils ---
  def TableExists(self, tableName: str):
    try:
      with self.conn.cursor() as cur:
        cur.execute(
          'SELECT * FROM information_schema.tables WHERE table_name=%s',
          (tableName,),
        )
        return self.__GenerateResponse(bool(cur.rowcount), '', generateLog=False)
    except psycopg2.Error as e:
      return self.__GenerateResponse(False, f'{e}')

  def __GenerateResponse(
    self, result: bool, message: str, extraData: dict = {}, generateLog=True
  ):
    """
    Private helper function to keep return message code DRY.
    Handles generating log messages for the action.
    Result == True: commit the change
    Result == False: rollback the change

    Args:
      result (bool): if the action was successful.
      message (str): the message to log and return
      extraData (dict): any extra information that should be returned
    Return:
      Object with both a result (bool) and message (str).
      Also returns extraData on the end if any passed
    """
    if not result:
      # If sql query fails for some reason, PostgreSQL aborts the transaction. If you don’t call conn.rollback(), every subsequent query fails as well.
      self.conn.rollback()
      if generateLog:
        self.log.GenerateLogMessage(message)
      return {'success': False, 'message': message, 'data': extraData}
    if generateLog:
      self.log.GenerateLogMessage(message)
    self.conn.commit()
    return {'success': True, 'message': message, 'data': extraData}
