"""Real MySQL integration tests. Uses a NEW disposable test database only.

Run from the project folder: .venv/bin/python -m unittest discover -s tests -v
The prepared assignment database and its images are never modified.
"""
import base64
from io import BytesIO
import os
from pathlib import Path
import sys
import tempfile
import unittest

from dotenv import dotenv_values
import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'website'))
from app import create_app

# A tiny, valid PNG fixture. Used only to test file uploads.
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')


class LibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        values = dotenv_values(ROOT / 'website' / '.env')
        cls.settings = dict(host=values.get('DB_HOST', '127.0.0.1'),
                            port=int(values.get('DB_PORT', 3306)),
                            user=values.get('DB_USER', 'root'),
                            password=values.get('DB_PASSWORD', ''), charset='utf8mb4')
        cls.test_db = f'library_lab3_2304066_test_{os.getpid()}'
        with pymysql.connect(**cls.settings) as conn, conn.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE {cls.test_db};')
            cursor.execute(f'USE {cls.test_db};')
            sql = '\n'.join(line for line in (ROOT / 'problem2_DDL.sql').read_text().splitlines()
                            if not line.lstrip().startswith('--'))
            for statement in sql.split(';'):
                if statement.strip().startswith('CREATE TABLE'):
                    cursor.execute(statement)
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        with pymysql.connect(**cls.settings) as conn, conn.cursor() as cursor:
            cursor.execute(f'DROP DATABASE {cls.test_db};')

    def setUp(self):
        self.uploads = tempfile.TemporaryDirectory()
        self.addCleanup(self.uploads.cleanup)
        self.app = create_app({'TESTING': True, 'DB_NAME': self.test_db,
                               'UPLOAD_FOLDER': self.uploads.name, 'SECRET_KEY': 'test-only-key'})
        self.client = self.app.test_client()
        with self.connect() as conn, conn.cursor() as cursor:
            cursor.execute('DELETE FROM BOOK;')
            cursor.execute('DELETE FROM AUTHOR;')
            sql = '\n'.join(line for line in (ROOT / 'problem2_DML.sql').read_text().splitlines()
                            if not line.lstrip().startswith('--'))
            for statement in sql.split(';'):
                if statement.strip().startswith('INSERT INTO'):
                    cursor.execute(statement)
            conn.commit()
        self.client.get('/library/authors/add')
        with self.client.session_transaction() as session:
            self.token = session['library_csrf']

    def connect(self):
        return pymysql.connect(**self.settings, database=self.test_db,
                               cursorclass=pymysql.cursors.DictCursor)

    def rows(self, sql, params=()):
        with self.connect() as conn, conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def post(self, path, data, **kwargs):
        data['csrf_token'] = self.token
        return self.client.post(path, data=data, **kwargs)

    def add_author(self, author_id=90, **kwargs):
        data = dict(author_id=str(author_id), name='Test Author', country='Egypt')
        data.update(kwargs)
        return self.post('/library/authors/add', data)

    def add_book(self, book_id=900, author_id=1, **kwargs):
        data = dict(book_id=str(book_id), title='Test Book', price='20.50', author_id=str(author_id))
        data.update(kwargs)
        return self.post('/library/books/add', data)

    def test_01_seed_schema_and_pages(self):
        self.assertEqual(len(self.rows('SELECT * FROM AUTHOR;')), 3)
        self.assertEqual(len(self.rows('SELECT * FROM BOOK;')), 6)
        self.assertEqual(len(self.rows('SHOW TABLES;')), 2)
        columns = self.rows('SHOW COLUMNS FROM BOOK;')
        self.assertEqual([row['Field'] for row in columns], ['book_id', 'title', 'price', 'author_id'])
        for path in ['/library/', '/library/books/add', '/library/authors/add',
                     '/library/books/101/edit', '/library/authors/1/edit', '/library/discussion']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        page = self.client.get('/library/').get_data(as_text=True)
        for value in ['Jana Bassem', '2304066', 'Farida Mohamed', '2304245', 'AUTHOR ID', 'Palace Walk']:
            self.assertIn(value.lower(), page.lower())

    def test_02_add_and_edit_both_records(self):
        self.assertEqual(self.add_author().status_code, 302)
        self.assertEqual(self.add_book(author_id=90).status_code, 302)
        self.assertEqual(self.post('/library/authors/90/edit', {'name': 'Updated Author', 'country': 'France'}).status_code, 302)
        self.assertEqual(self.post('/library/books/900/edit', {'title': 'Updated Book', 'price': '12.75', 'author_id': '2'}).status_code, 302)
        self.assertEqual(self.rows('SELECT name FROM AUTHOR WHERE author_id = 90;')[0]['name'], 'Updated Author')
        row = self.rows('SELECT * FROM BOOK WHERE book_id = 900;')[0]
        self.assertEqual(row['title'], 'Updated Book')
        self.assertEqual(str(row['price']), '12.75')
        self.assertEqual(row['author_id'], 2)

    def test_03_remove_book_preserves_author_and_other_books(self):
        self.add_book()
        self.assertEqual(self.post('/library/books/900/delete', {}).status_code, 302)
        self.assertEqual(self.rows('SELECT * FROM BOOK WHERE book_id = 900;'), ())
        self.assertEqual(len(self.rows('SELECT * FROM AUTHOR WHERE author_id = 1;')), 1)
        self.assertEqual(len(self.rows('SELECT * FROM BOOK;')), 6)

    def test_04_author_delete_cascades_and_cleans_images(self):
        self.add_author(image=(BytesIO(PNG), 'photo.png'))
        self.add_book(author_id=90, image=(BytesIO(PNG), 'cover.png'))
        preview = self.client.get('/library/authors/90/delete')
        self.assertIn(b'Test Book', preview.data)
        self.assertEqual(len(self.rows('SELECT * FROM AUTHOR WHERE author_id = 90;')), 1)
        self.assertEqual(self.post('/library/authors/90/delete', {}).status_code, 302)
        self.assertEqual(self.rows('SELECT * FROM AUTHOR WHERE author_id = 90;'), ())
        self.assertEqual(self.rows('SELECT * FROM BOOK WHERE author_id = 90;'), ())
        self.assertFalse((Path(self.uploads.name) / 'author-90.png').exists())
        self.assertFalse((Path(self.uploads.name) / 'book-900.png').exists())
        self.assertEqual(len(self.rows('SELECT * FROM BOOK;')), 6)

    def test_05_missing_author_rejected_by_mysql(self):
        response = self.add_book(author_id=9999)
        self.assertIn(b'This author does not exist', response.data)
        self.assertEqual(self.rows('SELECT * FROM BOOK WHERE book_id = 900;'), ())
        with self.connect() as conn, conn.cursor() as cursor:
            with self.assertRaises(pymysql.IntegrityError) as caught:
                cursor.execute("INSERT INTO BOOK VALUES (900, 'Bad reference', 10.00, 9999);")
            self.assertEqual(caught.exception.args[0], 1452)

    def test_06_duplicate_ids_are_clear(self):
        self.assertIn(b'author ID already exists', self.add_author(author_id=1).data)
        self.assertIn(b'book ID already exists', self.add_book(book_id=101).data)

    def test_07_price_text_and_id_validation(self):
        for price in ['-1', 'NaN', 'Infinity', '12.345', '100000000.00', 'abc']:
            with self.subTest(price=price):
                response = self.add_book(price=price)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.rows('SELECT * FROM BOOK WHERE book_id = 900;'), ())
        self.assertIn(b'Name is required', self.add_author(name='   ').data)
        self.assertIn(b'Country is required', self.add_author(country=' ').data)
        self.assertIn(b'Title is required', self.add_book(title=' ').data)
        self.assertIn(b'positive whole number', self.add_author(author_id='abc').data)
        self.assertEqual(self.add_book(price='0.00').status_code, 302)

    def test_08_both_bonus_uploads_persist_and_can_be_replaced(self):
        self.assertEqual(self.add_author(image=(BytesIO(PNG), 'photo.png')).status_code, 302)
        self.assertEqual(self.add_book(image=(BytesIO(PNG), 'cover.png')).status_code, 302)
        for kind, record_id in [('author', 90), ('book', 900)]:
            response = self.client.get(f'/library/image/{kind}/{record_id}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'image/png')
            response.close()
        page = self.client.get('/library/').data
        self.assertIn(b'Photo of Test Author', page)
        self.assertIn(b'Cover of Test Book', page)
        self.assertEqual(self.post('/library/books/900/edit', dict(title='Test Book', price='25.00', author_id='1', image=(BytesIO(PNG), 'new.png'))).status_code, 302)
        self.assertEqual(self.post('/library/authors/90/edit', dict(name='Test Author', country='Egypt', image=(BytesIO(PNG), 'new.png'))).status_code, 302)

    def test_09_images_can_be_removed_without_deleting_records(self):
        self.add_author(image=(BytesIO(PNG), 'photo.png'))
        self.add_book(image=(BytesIO(PNG), 'cover.png'))
        self.post('/library/authors/90/edit', dict(name='Test Author', country='Egypt', remove_image='1'))
        self.post('/library/books/900/edit', dict(title='Test Book', price='25.00', author_id='1', remove_image='1'))
        self.assertEqual(self.client.get('/library/image/author/90').status_code, 404)
        self.assertEqual(self.client.get('/library/image/book/900').status_code, 404)
        self.assertEqual(len(self.rows('SELECT * FROM AUTHOR WHERE author_id = 90;')), 1)
        self.assertEqual(len(self.rows('SELECT * FROM BOOK WHERE book_id = 900;')), 1)

    def test_10_invalid_images_and_large_uploads(self):
        self.assertIn(b'valid image', self.add_author(image=(BytesIO(b'not an image'), 'fake.png')).data)
        self.assertIn(b'Please upload a PNG', self.add_book(image=(BytesIO(b'text'), 'file.txt')).data)
        self.assertEqual(self.rows('SELECT * FROM AUTHOR WHERE author_id = 90;'), ())
        response = self.add_book(image=(BytesIO(b'x' * (5 * 1024 * 1024)), 'large.png'))
        self.assertEqual(response.status_code, 413)

    def test_11_missing_csrf_and_missing_records(self):
        response = self.client.post('/library/authors/add', data=dict(author_id=90, name='Bad form', country='Egypt'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.rows('SELECT * FROM AUTHOR WHERE author_id = 90;'), ())
        for path in ['/library/books/999/edit', '/library/authors/999/delete', '/library/image/other/1']:
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_12_parameterized_input_and_html_escaping(self):
        title = "<script>alert('x')</script> '; DELETE FROM AUTHOR; --"
        self.assertEqual(self.add_book(title=title).status_code, 302)
        self.assertEqual(self.rows('SELECT title FROM BOOK WHERE book_id = 900;')[0]['title'], title)
        self.assertEqual(len(self.rows('SELECT * FROM AUTHOR;')), 3)
        page = self.client.get('/library/').data
        self.assertIn(b'&lt;script&gt;', page)
        self.assertNotIn(b"<script>alert('x')</script>", page)


if __name__ == '__main__':
    unittest.main()
