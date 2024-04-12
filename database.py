# [[ NATIVE ]]
from typing import Union, Sequence, Any, Type, List
import traceback
import warnings
import os.path
import logging
import asyncio

# [[ SQLALCHEMY ]]
from sqlalchemy.ext.asyncio import create_async_engine, AsyncAttrs, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import ForeignKey, ChunkedIteratorResult, Result
from sqlalchemy import Select, Insert, Update, Delete
from sqlalchemy import select, insert, delete
from sqlalchemy.types import JSON
from sqlalchemy import or_

# [[ AIOMYSQL ]]
from aiomysql.sa import create_engine

# [[ SETTINGS ]]
from settings import DBType
from settings import DB_TYPE, DB_HOST, DB_USER, DB_PASS, DB_NAME

# [[ SETTING UP WARNINGS AND LOGGER ]]
warnings.filterwarnings('ignore')
logger = logging.getLogger()
logger.level = logging.INFO


class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for tables, added JSON support
    """
    __abstract__ = True
    type_annotation_map = {
        dict[str, Any]: JSON
    }

    def to_dict(self):
        return {field: getattr(self, field) for field in self.__table__.columns.keys()}

    # Fix for MySQL, query for creating table
    @staticmethod
    def mysql():
        ...


class Genres(Base):
    """
    Genres table
    """
    __tablename__ = 'genres'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)

    @staticmethod
    def mysql():
        return 'CREATE TABLE IF NOT EXISTS promo (' \
               'id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,' \
               'name TEXT NOT NULL)'


class Books(Base):
    """
    Books table
    """
    __tablename__ = 'books'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    author: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)

    @staticmethod
    def mysql():
        return 'CREATE TABLE IF NOT EXISTS users (' \
               'id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,' \
               'title TEXT NOT NULL,' \
               'author TEXT NOT NULL,' \
               'description TEXT NOT NULL)'


class BookGenre(Base):
    """
    Book genres table
    """
    __tablename__ = 'book_genre'

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[Books] = mapped_column(ForeignKey('books.id'))
    genre_id: Mapped[Genres] = mapped_column(ForeignKey('genres.id'))

    @staticmethod
    def mysql():
        return 'CREATE TABLE IF NOT EXISTS users (' \
               'id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,' \
               'book_id INTEGER NOT NULL,' \
               'genre_id INTEGER NOT NULL,' \
               'FOREIGN KEY (book_id) REFERENCES books (id),' \
               'FOREIGN KEY (genre_id) REFERENCES genres (id))'


class Database:
    """
    Main database class
    """
    def __init__(self):
        # Setting up main parameters
        self.db_url = None

        self.db_type: DBType = DB_TYPE

        self.db_name: str = DB_NAME
        self.db_user: str = DB_USER
        self.db_host: str = DB_HOST
        self.db_pass: str = DB_PASS

        # Declaring variables for SQLAlchemy
        self.engine = None
        self.session = None

    async def __start(self) -> None:
        """
        Starting database
        :return:
        """
        if self.db_type == DBType.SQLITE:
            self.db_url = 'sqlite+aiosqlite:///' + os.path.abspath(f'./{self.db_name}.db')
            self.engine = create_async_engine(self.db_url)
            self.session = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=True)

        elif self.db_type == DBType.MYSQL:
            # For MySQL no need creating engine
            # Session creating only before executing query
            pass

    async def __execute(self, query: Union[Select, Insert, Update, Delete], count=0) -> Union[Result, list, dict]:
        """
        Executing query
        :param query: Query
        :param count: Count of selecting rows
        :return: Rows or ID
        """
        if self.db_type == DBType.SQLITE:
            # Return ID of new row if executing INSERT INTO
            if not count:
                query = query.returning(getattr(await self.__get_table_by_name(query), 'id'))

            await self.__start()
            async with self.session() as session:
                session: AsyncSession
                result: Union[ChunkedIteratorResult, Result, List[dict], dict, None] = await session.execute(query)
                await session.flush()

                if not count:  # For INSERT INTO
                    try:
                        result = result.fetchone()[0]
                    except:
                        result = None
                elif count == 1:  # For SELECT one row
                    try:
                        result = result.fetchone()[0].to_dict()
                    except:
                        result = dict()
                elif count == -1:  # For SELECT all rows
                    try:
                        result = [item[0].to_dict() for item in result.fetchall()]
                    except:
                        result = [dict()]
                elif count > 1:  # For SELECT many rows
                    try:
                        result = [item[0].to_dict() for item in result.fetchmany(count)]
                    except:
                        result = [dict()]

                # Save changes after INSERT INTO or UPDATE or DELETE
                await session.commit()
        elif self.db_type == DBType.MYSQL:
            while True:
                # While DataBase is locked engine cannot create
                try:
                    self.engine = await create_engine(user=self.db_user, db=self.db_name, host=self.db_host, password=self.db_pass)
                    await asyncio.sleep(1)
                    break
                except Exception as exc:
                    print(exc)
                    pass

            async with self.engine.acquire() as conn:
                async with conn.begin() as transaction:
                    result_db = await conn.execute(query)
                    if not count:
                        # Returning id of new row after INSERT INTO
                        result_db = await conn.execute('SELECT LAST_INSERT_ID() as id')
                    # Save changes after INSERT INTO or UPDATE or DELETE
                    await transaction.commit()

                    # Transform rows to list of dicts
                    result = list()
                    async for row in result_db:
                        result.append(dict(row))

                    if not count:  # Return id
                        result = result[0]['id']
                    elif count == 1:  # Return one row
                        if not result:
                            result = None
                        else:
                            result = result[0]

        return result

    async def get_one(self, query: Union[Select]) -> dict:
        """
        SELECT one row
        :param query: Query
        :return: Row
        """
        return await self.__execute(query, 1)

    async def get_all(self, query: Union[Select]) -> list:
        """
        SELECT all rows
        :param query: Query
        :return: Rows
        """
        # Fix for returning all rows, if there are more than 1000
        if self.db_type == DBType.MYSQL:
            query = query.limit(18446744073709551610)
        elif self.db_type == DBType.SQLITE:
            query = query.limit(9223372036854775807)
        return await self.__execute(query, -1)

    async def get_many(self, query: Union[Select], count: int = 1) -> list:
        """
        SELECT many rows
        :param query: Query
        :param count: Count of rows for selecting
        :return: Rows
        """
        return await self.__execute(query, count)

    async def exec(self, query: Union[Insert, Update, Delete]) -> Any:
        """
        INSERT INTO or UPDATE or DELETE
        :param query: Query
        :return: Row ID
        """
        return await self.__execute(query)

    @staticmethod
    async def __get_table_by_name(query) -> Type[Base]:
        """
        Getting table object by name
        :param query: Query
        :return: Table object
        """
        for subclass in Base.__subclasses__():
            if hasattr(subclass, '__tablename__') and subclass.__tablename__ == str(query.table):
                return subclass

    async def __create_tables(self) -> None:
        """
        Create tables if not exists
        :return:
        """
        if self.db_type == DBType.SQLITE:
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        elif self.db_type == DBType.MYSQL:  # Fix for mysql, because SQLAlchemy cannot create table by metadata
            for subclass in Base.__subclasses__():
                if hasattr(subclass, '__tablename__'):
                    try:
                        logging.info('Initializing table {}'.format(subclass.__tablename__))
                        await self.__execute(subclass.mysql(), 0)  # noqa
                    except Exception as exc:
                        print(traceback.format_exception(exc))
                        print(subclass.mysql())
                        raise exc

    async def __insert_data(self) -> None:
        """
        Inserting default data
        :return:
        """

        """
        Example:
                
        data = (
            (func.now(), 1, 'text'),  # func.now - if need insert datetime.now()
            (func.now(), 2, 'blah'),
        )
        
        data_statement = (insert(Table).values(dt=dt, value=value, key=key).prefix_with('OR IGNORE') for dt, value, key in data)

        for statement in (statement_data,):
            for row in statement:
                # Inserting row from statement
                await session.execute(row)

        # Save changes
        await session.commit()
        """
        pass

    async def initialize(self) -> None:
        """
        Initializing database
        :return:
        """
        logging.info('Initializing database')

        await self.__start()
        await self.__create_tables()
        await self.__insert_data()

        logging.info('Database initialized')

    # [[ BOOKS ]]
    async def books_get(self, _id: int = None, title: str = None, author: str = None, genre_id: int = None):
        """
        Get books by parameters
        :param _id: Row ID
        :param title: Title of book
        :param author: Author of book
        :param genre_id: Genre ID of book
        :return: Row or Rows
        """
        query = select(Books)

        # If selecting book by id
        if _id is not None:
            return await self.get_one(query.where(Books.id == _id))

        # If selecting book by Title or Author
        if (title == author) and (title is not None):
            query = query.where(or_(Books.title.like('%{}%'.format(title)), Books.author.like('%{}%'.format(author))))
        else:
            if title is not None:
                query = query.where(Books.title.like('%{}%'.format(title)))
            if author is not None:
                query = query.where(Books.author.like('%{}%'.format(author)))

        # Filtering books by genre
        if genre_id is not None:
            query = query.join(BookGenre, Books.id == BookGenre.book_id)
            query = query.join(Genres, Genres.id == BookGenre.genre_id)
            query = query.where(Genres.id == genre_id)

        return await self.get_all(query)

    async def books_create(self, title: str, author: str, description: str):
        """
        Add new book
        :param title: Title of book
        :param author: Author of book
        :param description: Description of book
        :return: Row ID of new book
        """
        query = insert(Books).values(title=title, author=author, description=description)

        return await self.exec(query)

    async def books_delete(self, _id: int):
        """
        Delete book
        :param _id: Row ID
        :return:
        """
        query = delete(Books).where(Books.id == _id)

        return await self.exec(query)

    # [[ GENRES ]]
    async def genres_get(self, _id: int = None, name: str = None):
        """
        Get genres by ID or Name
        :param _id: Row ID
        :param name: Genre name
        :return: Row or Rows
        """
        query = select(Genres)

        if _id is not None:
            return await self.get_one(query.where(Genres.id == _id))

        if name is not None:
            query = query.where(Genres.name.like('%{}%'.format(name)))

        return await self.get_all(query)

    async def genres_create(self, name: str):
        """
        Add new genre
        :param name: Name of genre
        :return: Row ID of new genre
        """
        query = insert(Genres).values(name=name)

        return await self.exec(query)

    async def genres_delete(self, _id: int):
        """
        Delete genre
        :param _id: Row ID
        :return:
        """
        query = delete(Genres).where(Genres.id == _id)

        return await self.exec(query)

    # [[ BOOK GENRE ]]
    async def book_genre_get(self, _id: int = None, book_id: int = None, genre_id: int = None):
        """
        Get book genres
        :param _id: Row ID
        :param book_id: ID of book
        :param genre_id: ID of genre
        :return: Row or Rows
        """
        query = select(BookGenre)

        if _id is not None:
            return await self.get_one(query.where(BookGenre.id == _id))

        if book_id is not None:
            query = query.where(BookGenre.book_id == book_id)

        if genre_id is not None:
            query = query.where(BookGenre.genre_id == genre_id)

        return await self.get_all(query)

    async def book_genre_create(self, book_id: int, genre_id: int):
        """
        Create new book genre
        :param book_id: ID of book
        :param genre_id: ID of genre
        :return: Row ID of new book genre
        """
        query = insert(BookGenre).values(book_id=book_id, genre_id=genre_id)

        return await self.exec(query)

    async def book_genre_delete(self, _id: int):
        """
        Delete book genre
        :param _id: Row ID
        :return:
        """
        query = delete(BookGenre).where(BookGenre.id == _id)

        return await self.exec(query)


db = Database()


# [[ BOOKS ]]
async def books_get(_id: int = None, title: str = None, author: str = None, genre_id: int = None):
    """
    Get books from database
    :param _id: Row ID
    :param title: Title of book
    :param author: Author of book
    :param genre_id: Description of book
    :return: Row or Rows
    """
    return await db.books_get(_id=_id, title=title, author=author, genre_id=genre_id)


async def books_add(title: str, author: str, description: str, genres_id: Sequence[int]):
    """
    Add new book
    :param title: Title of book
    :param author: Author of book
    :param description: Description of book
    :param genres_id: Genres of book
    :return: Row ID of new book
    """
    book_id = await db.books_create(title=title, author=author, description=description)

    for genre_id in genres_id:
        await db.book_genre_create(book_id=book_id, genre_id=genre_id)

    return book_id


async def books_delete(_id: int):
    """
    Delete book
    :param _id: Row ID
    :return:
    """
    await db.books_delete(_id=_id)

    book_genres = await db.book_genre_get(book_id=_id)
    for book_genre in book_genres:
        await db.book_genre_delete(_id=book_genre['id'])


# [[ GENRES ]]
async def genres_get(_id: int = None, name: str = None):
    """
    Get genre
    :param _id: Row ID
    :param name: Name of genre
    :return: Row or Rows
    """
    return await db.genres_get(_id=_id, name=name)


async def genres_add(name: str):
    """
    Add new genre
    :param name: Name of genre
    :return: Row ID
    """
    return await db.genres_create(name=name)


# [[ BOOK GENRE ]]
async def book_genre_get(book_id: int):
    """
    Get book genre
    :param book_id: Row ID of book
    :return: Row or Rows
    """
    return await db.book_genre_get(book_id=book_id)
