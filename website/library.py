"""Part II pages. All application queries use simple SELECT/INSERT/UPDATE/DELETE.

Images live in files, keeping the exact two-table schema required by the lab.
The blueprint can also be registered in an existing Flask Lab 2 application.
"""
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
import secrets
import warnings

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, send_file, session, url_for,
)
from PIL import Image, UnidentifiedImageError
import pymysql

library = Blueprint('library', __name__, template_folder='templates')


@contextmanager
def database():
    """Open one MySQL connection and always close it after the request."""
    connection = pymysql.connect(
        host=current_app.config['DB_HOST'], port=current_app.config['DB_PORT'],
        user=current_app.config['DB_USER'], password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME'], charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5,
    )
    try:
        yield connection
    finally:
        connection.close()


def csrf_token():
    if 'library_csrf' not in session:
        session['library_csrf'] = secrets.token_hex(24)
    return session['library_csrf']


@library.context_processor
def template_helpers():
    return {'csrf_token': csrf_token}


@library.before_request
def protect_forms():
    if request.method == 'POST':
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(supplied, session.get('library_csrf', 'missing')):
            abort(400, 'The form expired. Reload the page and try again.')


def positive_id(value, label):
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise ValueError(f'{label} must be a positive whole number.')
    if not 1 <= result <= 2147483647:
        raise ValueError(f'{label} must be between 1 and 2147483647.')
    return result


def required_text(value, label, maximum):
    result = value.strip()
    if not result:
        raise ValueError(f'{label} is required.')
    if len(result) > maximum:
        raise ValueError(f'{label} must be {maximum} characters or fewer.')
    return result


def valid_price(value):
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError('Enter a valid price, for example 18.50.')
    if not result.is_finite() or result < 0 or result > Decimal('99999999.99'):
        raise ValueError('Price must be between 0.00 and 99999999.99.')
    if result != result.quantize(Decimal('0.01')):
        raise ValueError('Price can have at most two decimal places.')
    return result


def uploaded_image():
    """Verify file contents, then normalize uploads to a local PNG file."""
    upload = request.files.get('image')
    if not upload or not upload.filename:
        return None
    if Path(upload.filename).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
        raise ValueError('Please upload a PNG, JPG or WebP image.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload.stream) as source:
                if source.format not in {'PNG', 'JPEG', 'WEBP'}:
                    raise ValueError('The file must contain a PNG, JPG or WebP image.')
                if source.width * source.height > 20_000_000:
                    raise ValueError('Choose an image smaller than 20 megapixels.')
                source.load()
                picture = source.convert('RGB')
                picture.thumbnail((1200, 1200))
                buffer = BytesIO()
                picture.save(buffer, format='PNG')
                return buffer.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise ValueError('This image could not be read. Please choose a valid image.')


def image_path(kind, record_id):
    return Path(current_app.config['UPLOAD_FOLDER']) / f'{kind}-{record_id}.png'


def store_image(kind, record_id, image_data):
    target = image_path(kind, record_id)
    # A temporary file prevents a partially written image from being displayed.
    temporary = target.with_suffix('.tmp')
    temporary.write_bytes(image_data)
    temporary.replace(target)


def image_exists(kind, record_id):
    return image_path(kind, record_id).is_file()


@library.route('/image/<kind>/<int:record_id>')
def image(kind, record_id):
    if kind not in {'book', 'author'} or not image_exists(kind, record_id):
        abort(404)
    response = send_file(image_path(kind, record_id), mimetype='image/png', max_age=0)
    response.headers['Cache-Control'] = 'no-store'
    return response


@library.route('/')
def catalog():
    with database() as connection, connection.cursor() as cursor:
        # F2.1: separate tables, with author_id explicitly visible on each book.
        cursor.execute('SELECT book_id, title, price, author_id FROM BOOK;')
        books = list(cursor.fetchall())
        cursor.execute('SELECT author_id, name, country FROM AUTHOR;')
        authors = list(cursor.fetchall())
    # Display ordering and counts happen in Python, not advanced SQL.
    books.sort(key=lambda row: row['book_id'])
    authors.sort(key=lambda row: row['author_id'])
    for row in books:
        row['has_image'] = image_exists('book', row['book_id'])
    for row in authors:
        row['has_image'] = image_exists('author', row['author_id'])
        row['book_count'] = sum(book['author_id'] == row['author_id'] for book in books)
    return render_template('catalog.html', books=books, authors=authors)


@library.route('/authors/add', methods=['GET', 'POST'])
@library.route('/authors/<int:record_id>/edit', methods=['GET', 'POST'])
def author_form(record_id=None):
    author = None
    if record_id is not None:
        with database() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT author_id, name, country FROM AUTHOR WHERE author_id = %s;',
                           (record_id,))
            author = cursor.fetchone()
        if author is None:
            abort(404)
    error = None
    values = request.form if request.method == 'POST' else (author or {})
    if request.method == 'POST':
        try:
            author_id = record_id if record_id is not None else positive_id(
                request.form.get('author_id'), 'Author ID')
            name = required_text(request.form.get('name', ''), 'Name', 100)
            country = required_text(request.form.get('country', ''), 'Country', 50)
            photo = uploaded_image()
            with database() as connection, connection.cursor() as cursor:
                if record_id is None:
                    cursor.execute('INSERT INTO AUTHOR (author_id, name, country) VALUES (%s, %s, %s);',
                                   (author_id, name, country))
                else:
                    cursor.execute('UPDATE AUTHOR SET name = %s, country = %s WHERE author_id = %s;',
                                   (name, country, author_id))
                connection.commit()
            if photo is not None:
                store_image('author', author_id, photo)
            elif request.form.get('remove_image'):
                image_path('author', author_id).unlink(missing_ok=True)
            flash('Author added.' if record_id is None else 'Author updated.', 'success')
            return redirect(url_for('library.catalog', _anchor='authors'))
        except ValueError as exc:
            error = str(exc)
        except pymysql.IntegrityError as exc:
            if exc.args[0] != 1062:
                raise
            error = 'That author ID already exists. Choose a different ID.'
    return render_template('record_form.html', kind='author', record=author,
                           values=values, error=error, authors=[],
                           has_image=record_id is not None and image_exists('author', record_id))


@library.route('/books/add', methods=['GET', 'POST'])
@library.route('/books/<int:record_id>/edit', methods=['GET', 'POST'])
def book_form(record_id=None):
    with database() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT author_id, name, country FROM AUTHOR;')
        authors = list(cursor.fetchall())
        book = None
        if record_id is not None:
            cursor.execute('SELECT book_id, title, price, author_id FROM BOOK WHERE book_id = %s;',
                           (record_id,))
            book = cursor.fetchone()
            if book is None:
                abort(404)
    authors.sort(key=lambda row: row['author_id'])
    error = None
    values = request.form if request.method == 'POST' else (book or {})
    if request.method == 'POST':
        try:
            book_id = record_id if record_id is not None else positive_id(
                request.form.get('book_id'), 'Book ID')
            title = required_text(request.form.get('title', ''), 'Title', 150)
            price = valid_price(request.form.get('price', ''))
            author_id = positive_id(request.form.get('author_id'), 'Author ID')
            cover = uploaded_image()
            with database() as connection, connection.cursor() as cursor:
                if record_id is None:
                    cursor.execute('INSERT INTO BOOK (book_id, title, price, author_id) VALUES (%s, %s, %s, %s);',
                                   (book_id, title, price, author_id))
                else:
                    cursor.execute('UPDATE BOOK SET title = %s, price = %s, author_id = %s WHERE book_id = %s;',
                                   (title, price, author_id, book_id))
                connection.commit()
            if cover is not None:
                store_image('book', book_id, cover)
            elif request.form.get('remove_image'):
                image_path('book', book_id).unlink(missing_ok=True)
            flash('Book added.' if record_id is None else 'Book updated.', 'success')
            return redirect(url_for('library.catalog', _anchor='books'))
        except ValueError as exc:
            error = str(exc)
        except pymysql.IntegrityError as exc:
            if exc.args[0] == 1062:
                error = 'That book ID already exists. Choose a different ID.'
            elif exc.args[0] == 1452:
                error = 'This author does not exist. Add an author first or choose an existing one.'
            else:
                raise
    return render_template('record_form.html', kind='book', record=book,
                           values=values, error=error, authors=authors,
                           has_image=record_id is not None and image_exists('book', record_id))


@library.route('/books/<int:record_id>/delete', methods=['GET', 'POST'])
def delete_book(record_id):
    with database() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT book_id, title, price, author_id FROM BOOK WHERE book_id = %s;',
                       (record_id,))
        book = cursor.fetchone()
        if book is None:
            abort(404)
        if request.method == 'POST':
            cursor.execute('DELETE FROM BOOK WHERE book_id = %s;', (record_id,))
            connection.commit()
            image_path('book', record_id).unlink(missing_ok=True)
            flash('Book removed. Its author is unchanged.', 'success')
            return redirect(url_for('library.catalog', _anchor='books'))
    return render_template('delete.html', kind='book', record=book, books=[])


@library.route('/authors/<int:record_id>/delete', methods=['GET', 'POST'])
def delete_author(record_id):
    with database() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT author_id, name, country FROM AUTHOR WHERE author_id = %s;',
                       (record_id,))
        author = cursor.fetchone()
        if author is None:
            abort(404)
        cursor.execute('SELECT book_id, title, price, author_id FROM BOOK WHERE author_id = %s;',
                       (record_id,))
        books = list(cursor.fetchall())
        if request.method == 'POST':
            # F2.5: only delete the author. MySQL cascades the BOOK deletions.
            cursor.execute('DELETE FROM AUTHOR WHERE author_id = %s;', (record_id,))
            connection.commit()
            image_path('author', record_id).unlink(missing_ok=True)
            for book in books:
                image_path('book', book['book_id']).unlink(missing_ok=True)
            flash(f'Author and {len(books)} associated book(s) removed.', 'success')
            return redirect(url_for('library.catalog', _anchor='authors'))
    return render_template('delete.html', kind='author', record=author, books=books)


@library.route('/discussion')
def discussion():
    return render_template('discussion.html')


@library.errorhandler(pymysql.MySQLError)
def database_error(exc):
    # Log the numeric code only; never display connection credentials.
    current_app.logger.error('Library database error code: %s', exc.args[0])
    return render_template('message.html', title='Database connection needs attention',
                           message='Check website/.env and make sure MySQL is running. '
                           'Run the DDL and DML scripts once, then reload this page.'), 503


@library.app_errorhandler(413)
def image_too_large(exc):
    return render_template('message.html', title='That upload is too large',
                           message='Choose an image smaller than 5 MB, then return to the form.'), 413


@library.app_errorhandler(404)
def page_not_found(exc):
    return render_template('message.html', title='Record not found',
                           message='This page or record is no longer available. Return to the library.'), 404


@library.app_errorhandler(400)
def invalid_form(exc):
    return render_template('message.html', title='Please reload the form',
                           message='The form could not be submitted. Reload the page and try again.'), 400
