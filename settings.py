# Enum of DataBase types
class DBType:
    SQLITE = 1
    MYSQL = 2


# [[ SETTINGS . DATABASE ]]
DB_TYPE = DBType.SQLITE

DB_HOST = '127.0.0.1'
DB_USER = 'library_user'
DB_PASS = 'library_pass'
DB_NAME = 'library'
