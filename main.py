# [[ NATIVE ]]
from typing import Sequence, Union
import asyncio
import sys

# [[ KIVY ]]
import kivy

from kivy.app import App

from kivy.core.window import Window

# [[ KIVY . LAYOUTS ]]
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout

# [[ KIVY UI ]]
from kivy.uix.behaviors.button import ButtonBehavior
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.dropdown import DropDown
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.popup import Popup

# [[ DATABASE ]]
import database as db

# [[ CODE ]]
kivy.require('2.3.0')

# [[ WINDOW SETTINGS ]]
Window.set_title('Library database')
Window.size = (800, 400)
Window.minimum_width, Window.minimum_height = (800, 400)
Window.clearcolor = (0.15, 0.1, 0.25, 1)


# [[ OBJECTS ]]
class ViewBookDialog(Popup):
    """
    Window for view information about book
    """
    def __init__(self, main_widget: 'BookLine', **kwargs):
        super(ViewBookDialog, self).__init__(**kwargs)

        # Setting up layout
        self.title = main_widget.title
        self.content = BoxLayout(orientation='vertical')
        self.text_content = BoxLayout(orientation='vertical',
                                      size_hint_y=None,
                                      height=(len(main_widget.description) // 40) * 33)
        self.container = ScrollView(do_scroll_y=True, do_scroll_x=False)
        self.size_hint = (None, None)
        self.size = (400, 400)

        # Fix height if description is small
        if self.text_content.height < 150:
            self.text_content.height = 150

        # Declaring UI objects
        self.label_author = Label(text='Author: ' + main_widget.author,
                                  size_hint_max_y=35,
                                  halign='left',
                                  valign='middle')
        self.label_genres = Label(text='Genres: ' + main_widget.genres,
                                  size_hint_max_y=35,
                                  halign='left',
                                  valign='middle')
        self.label_description = Label(text='Description:\n' + main_widget.description,
                                       halign='left',
                                       valign='top')

        # Fix for labels, it needed for correct work left align
        self.label_author.bind(size=self.label_author.setter('text_size'))
        self.label_genres.bind(size=self.label_genres.setter('text_size'))
        self.label_description.bind(size=self.label_description.setter('text_size'))

        # Adding widgets to layout
        self.text_content.add_widget(self.label_author)
        self.text_content.add_widget(self.label_genres)
        self.text_content.add_widget(self.label_description)
        self.container.add_widget(self.text_content)

        self.content.add_widget(self.container)
        self.content.add_widget(Button(text='Close', on_release=self.dismiss, size_hint_max_y=50))


class BookLine(ButtonBehavior, GridLayout):
    """
    Line with small information about book, for list of books
    """
    def __init__(self, main_widget: 'BooksList' = None, **kwargs):
        super(BookLine, self).__init__(**kwargs)

        # For access to parent object
        self.main_widget = main_widget

        # Setting up layout
        self.cols = 2
        self.size_hint_max_y = 100
        self.size_hint_min_y = 100

        # Defining information about book
        self.author = 'Author'
        self.title = 'Title'
        self.description = 'Description'
        self.genres = 'Genres'

        self.book_id = None

    async def create(self, book_id: int) -> 'BookLine':
        """
        Construct line with book information
        :param book_id: ID of book from database
        :return:
        """
        self.book_id = book_id

        # Getting information about book
        book = await db.books_get(_id=book_id)
        genres_id = await db.book_genre_get(book_id=book_id)
        genres = [await db.genres_get(_id=row['genre_id']) for row in genres_id]
        genres = ', '.join([genre['name'] for genre in genres])

        # Declaring UI objects
        label_title = Label(text=book['title'], halign='left', valign='middle', font_size=24)
        label_author = Label(text='Author: ' + book['author'], halign='left', valign='top', padding=(10, 0, 0, 0))

        book_layout = BoxLayout(orientation='vertical', size_hint_max_y=100, padding=(10, 10, 10, 0))
        book_layout.add_widget(label_title)
        book_layout.add_widget(label_author)

        label_title.bind(size=label_title.setter('text_size'))
        label_author.bind(size=label_author.setter('text_size'))

        # For access from ViewBookDialog
        self.author = book['author']
        self.title = book['title']
        self.genres = genres
        self.description = book['description']

        # Adding widgets to layout
        self.add_widget(book_layout)
        self.add_widget(Button(text='X', on_release=self.delete, size_hint_max_x=100, size_hint_min_x=100))

        return self

    def delete(self, instance: Button) -> None:
        """
        [Event] Delete book from database and update list of books from main layout
        :param instance: Button object
        :return:
        """
        asyncio.run(db.books_delete(_id=self.book_id))
        self.main_widget.main_widget.search_book()

    def on_release(self) -> None:
        """
        [Event] Open information about book if line is clicked
        :return:
        """
        ViewBookDialog(self).open()


class BooksList(GridLayout):
    """
    Layout for costruct list of books
    """
    def __init__(self, main_widget: 'MainScreen', **kwargs):
        super(BooksList, self).__init__(**kwargs)

        # For access to parent object
        self.main_widget = main_widget

        # Setting up layout
        self.cols = 1
        self.spacing = (5, 5,)

        self.books_count = 0

        asyncio.run(self.load_books())

    async def load_books(self, search_string: str = None, genre_id: int = None) -> None:
        """
        Loading books and creating BookLine for this list
        :param search_string: Text for search by Author or Title of book
        :param genre_id: Genre ID for search by genre
        :return:
        """
        self.clear_widgets()

        books = await db.books_get(title=search_string, author=search_string, genre_id=genre_id)
        self.books_count = len(books)
        for book in books:
            book_line = await BookLine(self).create(book['id'])
            self.add_widget(book_line)


class AddGenreDialog(Popup):
    """
    Dialog for adding genre to new book
    """
    def __init__(self, main_widget: 'AddBookDialog', **kwargs):
        super(AddGenreDialog, self).__init__(**kwargs)

        # For access to parent object
        self.main_widget = main_widget

        # Setting up layout
        self.title = 'Add genre'
        self.content = BoxLayout(orientation='vertical', spacing=5)
        self.size_hint = (None, None)
        self.size = (400, 400)

        self.genre_id = None

        # Declaring UI objects
        self.checkbox_exists = CheckBox(group='check', size_hint_max_x=20, allow_no_selection=False, active=True)
        self.checkbox_new = CheckBox(group='check', size_hint_max_x=20, allow_no_selection=False)

        self.checkbox_exists.bind(active=self.on_exists)
        self.checkbox_new.bind(active=self.on_new)

        self.label_exists = Label(text='Exists genre', halign='left', valign='middle', padding=(10, 0, 0, 0))
        self.label_new = Label(text='New genre', halign='left', valign='middle', padding=(10, 0, 0, 0))

        self.label_exists.bind(size=self.label_exists.setter('text_size'))
        self.label_new.bind(size=self.label_new.setter('text_size'))

        self.layout_exists = BoxLayout(orientation='horizontal', size_hint_max_y=35)
        self.layout_exists.add_widget(self.checkbox_exists)
        self.layout_exists.add_widget(self.label_exists)

        self.layout_new = BoxLayout(orientation='horizontal', size_hint_max_y=35)
        self.layout_new.add_widget(self.checkbox_new)
        self.layout_new.add_widget(self.label_new)

        self.dropdown = DropDown(on_select=self.select_genre)
        self.dropdown_btn = Button(text='Choose', on_release=self.dropdown.open, size_hint_max_y=50)

        genres = asyncio.run(db.genres_get())
        for genre in genres:
            btn = Button(text=genre['name'],
                         size_hint_y=None,
                         height=40,
                         on_release=lambda instance: self.dropdown.select(instance.text))
            self.dropdown.add_widget(btn)

        self.textinput_genre = TextInput(hint_text='Genre', size_hint_max_y=35)
        self.textinput_genre.bind(text=self.write_genre)

        self.btn_add = Button(text='Add', on_release=self.add_genre, size_hint_max_y=35, disabled=True)

        # Adding widgets to layout
        self.content.add_widget(self.layout_exists)
        self.content.add_widget(self.layout_new)
        self.content.add_widget(self.dropdown_btn)
        self.content.add_widget(Widget())
        self.content.add_widget(self.btn_add)
        self.content.add_widget(Button(text='Cancel', on_release=self.on_close, size_hint_max_y=35))

    def on_close(self, instance: Button) -> None:
        """
        [Event] Close this popup
        :param instance: Button object
        :return:
        """
        self.checkbox_exists.active = True
        self.checkbox_new.active = False

        self.update(self.dropdown_btn)

        self.dismiss()

    def add_genre(self, instance: Button) -> None:
        """
        [Event] Add genre to new book and close popup
        :param instance: Button object
        :return:
        """

        # Fix checkboxes for next times
        self.checkbox_exists.active = True
        self.checkbox_new.active = False

        # If user entered new genre, adding this to database
        if self.textinput_genre.text:
            self.genre_id = asyncio.run(db.genres_add(name=self.textinput_genre.text))

        # Getting genre information from database
        genre = asyncio.run(db.genres_get(_id=self.genre_id))['name']

        # Refresh data for next times
        self.genre_id = None
        self.textinput_genre.text = ''
        self.dropdown_btn.text = 'Choose'
        self.btn_add.disabled = True

        self.update(self.dropdown_btn)

        # Adding genre to new book
        self.main_widget.genres.append(genre)
        self.main_widget.validate()
        self.main_widget.update()

        # Updating dropdown, adding new genre, if it is new
        self.dropdown.clear_widgets()
        genres = asyncio.run(db.genres_get())
        for genre in genres:
            btn = Button(text=genre['name'],
                         size_hint_y=None,
                         height=40,
                         on_release=lambda instance: self.dropdown.select(instance.text))
            if genre['name'] in self.main_widget.genres:
                btn.disabled = True
            self.dropdown.add_widget(btn)

        self.dismiss()

    def on_exists(self, instance: CheckBox, value: bool) -> None:
        """
        [Event] If user choose exists genre
        :param instance: CheckBox object
        :param value: Value of CheckBox
        :return:
        """
        # Fix, if checkbox is disabled, because its hook called from group
        if not value:
            return

        # Refresh values for correct work
        self.dropdown_btn.text = 'Choose'

        self.btn_add.disabled = True

        self.update(self.dropdown_btn)

    def on_new(self, instance: CheckBox, value: bool) -> None:
        """
        [Event] If user choose exists genre
        :param instance: CheckBox object
        :param value: Value of CheckBox
        :return:
        """
        # Fix, if checkbox is disabled, because its hook called from group
        if not value:
            return

        # Refresh values for correct work
        self.genre_id = None
        self.textinput_genre.text = ''

        self.btn_add.disabled = True

        self.update(self.textinput_genre)

    def select_genre(self, instance: DropDown, genre_name: str) -> None:
        """
        [Event] If user select genre from exists
        :param instance: DropDown object
        :param genre_name: Value of DropDown element
        :return:
        """
        # If this method called without selecting
        if genre_name is not None:
            self.dropdown_btn.text = genre_name

        self.genre_id = asyncio.run(db.genres_get(name=genre_name))[0]['id']

        # Disable "Add" button if user not chosen genre
        self.btn_add.disabled = False

    def write_genre(self, instance: TextInput, genre_name: str) -> None:
        """
        [Event] If user writing new genre
        :param instance: TextInput object
        :param genre_name: Writed text
        :return:
        """
        if genre_name:
            self.btn_add.disabled = False

        # Disable "Add" button if text is ""
        self.btn_add.disabled = not len(genre_name)

    def update(self, widget: Union[DropDown, TextInput]) -> None:
        """
        Update layout UI
        :param widget: DropDown or TextInput object, depending on the checkbox
        :return:
        """
        self.content.clear_widgets()

        self.content.add_widget(self.layout_exists)
        self.content.add_widget(self.layout_new)
        self.content.add_widget(widget)
        self.content.add_widget(Widget())
        self.content.add_widget(self.btn_add)
        self.content.add_widget(Button(text='Cancel', on_release=self.on_close, size_hint_max_y=35))


class AddBookDialog(Popup):
    """
    If user clicked "+", for add new book
    """
    def __init__(self, main_widget: 'MainScreen', **kwargs):
        super(AddBookDialog, self).__init__(**kwargs)

        # For access to parent object
        self.main_widget = main_widget

        # Setting up layout
        self.title = 'Add new book'
        self.content = BoxLayout(orientation='vertical', spacing=5)
        self.size_hint = (None, None)
        self.size = (400, 400)

        self.genres = list()

        # Declaring UI objects
        self.popup = AddGenreDialog(self)

        self.input_author = TextInput(hint_text='Author', multiline=False, size_hint_max_y=35)
        self.input_title = TextInput(hint_text='Title', multiline=False, size_hint_max_y=35)
        self.input_description = TextInput(hint_text='Description', size_hint_max_y=70)

        self.input_author.bind(text=self.validate)
        self.input_title.bind(text=self.validate)
        self.input_description.bind(text=self.validate)

        self.label_genres = Label(text='Genres: ', size_hint_max_y=35, halign='left', valign='middle')
        self.label_genres.bind(size=self.label_genres.setter('text_size'))
        self.btn_genres = Button(text='Add Genre', size_hint_max_y=35, on_release=self.popup.open)

        self.btn_add = Button(text='Add', on_release=self.add_book, size_hint_max_y=35, disabled=True)

        # Adding widgets to layout
        self.content.add_widget(self.input_author)
        self.content.add_widget(self.input_title)
        self.content.add_widget(self.label_genres)
        self.content.add_widget(self.btn_genres)
        self.content.add_widget(self.input_description)
        self.content.add_widget(self.btn_add)
        self.content.add_widget(Button(text='Cancel', on_release=self.on_close, size_hint_max_y=35))

    def on_close(self, instance: Button) -> None:
        """
        [Event] If user closed this popup
        :param instance: Button object
        :return:
        """
        # Refresh values for next times
        self.update()
        self.input_author.text = ''
        self.input_title.text = ''
        self.input_description.text = ''
        self.label_genres.text = 'Genres: '
        self.dismiss()

    def add_book(self, instance: Button) -> None:
        """
        [Event] If user add new book
        :param instance: Button object
        :return:
        """
        # Add new book to database, and add chosen genres
        genres_id = [asyncio.run(db.genres_get(name=genre))[0]['id'] for genre in self.genres]
        self.main_widget.add_book(author=self.input_author.text,
                                  title=self.input_title.text,
                                  genres_id=genres_id,
                                  description=self.input_description.text)

        self.input_author.text = ''
        self.input_title.text = ''
        self.input_description.text = ''
        self.dismiss()

    def validate(self, instance: TextInput = None, text: str = None) -> None:
        """
        [Event] Validate values for disable or enable "Add" button
        :param instance: TextInput object, if it is called from TextInput hook, else None, if it called outside event
        :param text: TextInput value or nothing, if it called outside event
        :return:
        """
        self.update()
        self.btn_add.disabled = not (self.input_title.text and
                                     self.input_author.text and
                                     self.input_description.text and
                                     self.label_genres.text != 'Genres: ')

    def update(self) -> None:
        """
        Updating layout UI
        :return:
        """
        self.content.clear_widgets()

        # Adding selected genres to Genres label
        self.label_genres.text = 'Genres: ' + ', '.join(self.genres)

        self.content.add_widget(self.input_author)
        self.content.add_widget(self.input_title)
        self.content.add_widget(self.label_genres)
        self.content.add_widget(self.btn_genres)
        self.content.add_widget(self.input_description)
        self.content.add_widget(self.btn_add)
        self.content.add_widget(Button(text='Cancel', on_release=self.on_close, size_hint_max_y=35))

        self.main_widget.update()


class MainScreen(GridLayout):
    """
    Main layout
    """
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)

        # Setting up layout
        self.rows = 2
        self.padding = (5, 5, 5, 5)

        # Declaring and setting up UI objects
        self.popup = AddBookDialog(self)

        self.scrollview = ScrollView(do_scroll_y=True, do_scroll_x=False)

        self.books_list = BooksList(self, size_hint_y=None)

        self.panel = BoxLayout(size_hint_max_y=50)

        self.dropdown = DropDown(on_select=self.select_genre)
        self.dropdown_btn = Button(text='All', on_release=self.dropdown.open, size_hint_max_x=150)

        self.text_input_search = TextInput(hint_text='Search by title or author', multiline=False, font_size=32)
        self.text_input_search.bind(text=self.search_book)
        self.panel.add_widget(self.text_input_search)
        self.panel.add_widget(self.dropdown_btn)
        self.panel.add_widget(Button(text='+', size_hint_max_x=50, on_release=self.popup.open))

        self.scrollview.add_widget(self.books_list)

        # Adding widgets to layout
        self.add_widget(self.scrollview)
        self.add_widget(self.panel)

        self.select_genre()

    def search_book(self, instance: TextInput = None, text: str = None, genre: str = None) -> None:
        """
        Search books by Title/Author/Genre
        :param instance: TextInput object
        :param text: Text of TextInput for search
        :param genre: Selected genre for search
        :return:
        """
        self.clear_widgets()

        # Text is none only when this method calls outside event
        if text is None:
            if instance is not None:
                text = instance.text
            else:
                text = self.text_input_search.text

        # Getting genre from dropdown if it was not passed
        if genre is None:
            genre = self.dropdown_btn.text
        genre_id = asyncio.run(db.genres_get(name=genre))[0]['id'] if genre != 'All' else None

        # Getting books by filters from database
        asyncio.run(self.books_list.load_books(text or None, genre_id))

        # Setting up height for books list, it needed for correct work ScrollView
        self.books_list.height = self.books_list.books_count * BookLine().height + \
                                 self.books_list.spacing[0] * (self.books_list.books_count - 1)

        # Adding widgets to layout
        self.add_widget(self.scrollview)
        self.add_widget(self.panel)

    def add_book(self, title: str, author: str, genres_id: Sequence[int], description: str) -> None:
        """
        Adding new book
        :param title: Title of book
        :param author: Author of book
        :param genres_id: Genres of book
        :param description: Description of book
        :return:
        """
        asyncio.run(db.books_add(title=title, author=author, genres_id=genres_id, description=description))
        self.search_book()

    def select_genre(self, instance: DropDown = None, genre_name: str = None) -> None:
        """
        [Event] Selecting genre in DropDown menu (filter books by genre)
        :param instance: DropDown object
        :param genre_name: Selected value from DropDrown
        :return:
        """
        if genre_name is not None:
            self.dropdown_btn.text = genre_name

        self.update()

        self.search_book(genre=genre_name)

    def update(self) -> None:
        """
        Updating MainScreen layout after making changes
        :return:
        """
        self.clear_widgets()

        # Adding genres for dropdown menu (filter books by genre)
        self.dropdown.clear_widgets()
        genres = [{'name': 'All'}] + asyncio.run(db.genres_get())
        for genre in genres:
            btn = Button(text=genre['name'],
                         size_hint_y=None,
                         height=40,
                         on_release=lambda instance: self.dropdown.select(instance.text))
            if genre['name'] == self.dropdown_btn.text:
                btn.disabled = True
            self.dropdown.add_widget(btn)

        # Adding widgets to layout
        self.add_widget(self.scrollview)
        self.add_widget(self.panel)


class BooksApp(App):
    """
    Main class for UI
    """
    def build(self) -> MainScreen:
        """
        Building app UI
        :return:
        """
        self.title = 'Library database'
        return MainScreen()


async def main() -> None:
    """
    Running asynchronous functions
    :return:
    """
    await db.Database().initialize()


if __name__ == '__main__':
    # Creating event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        #################
        # START Fix for Windows
        if sys.platform in ('win32', 'cygwin',):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # END Fix for Windows
        #################

        # Creating coroutines
        loop = asyncio.get_event_loop()
        coro = asyncio.wait([
            loop.create_task(main())
        ])

        # Running coroutines
        loop.run_until_complete(coro)
    except KeyboardInterrupt:
        pass

    # Running window app
    app = BooksApp()
    app.run()
