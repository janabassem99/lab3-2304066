"""Verify navigation and login persistence across both mounted labs in MySQL."""
import os
from pathlib import Path
import re
import sys
import unittest

from dotenv import dotenv_values
import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'website'))
from app import create_app


class CombinedLabsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        values = dotenv_values(ROOT / 'website/.env')
        cls.settings = dict(host=values.get('DB_HOST', '127.0.0.1'),
                            port=int(values.get('DB_PORT', 3306)),
                            user=values.get('DB_USER', 'root'),
                            password=values.get('DB_PASSWORD', ''), charset='utf8mb4')
        cls.test_db = f'lab_bridge_test_{os.getpid()}'
        with pymysql.connect(**cls.settings) as connection, connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE {cls.test_db};')
            cursor.execute(f'USE {cls.test_db};')
            for file in [ROOT / 'problem2_DDL.sql', ROOT / 'website/lab2/database/schema.sql']:
                sql = '\n'.join(line for line in file.read_text().splitlines()
                                if not line.lstrip().startswith('--'))
                for statement in sql.split(';'):
                    if statement.strip().startswith('CREATE TABLE'):
                        cursor.execute(statement)
            connection.commit()

    @classmethod
    def tearDownClass(cls):
        with pymysql.connect(**cls.settings) as connection, connection.cursor() as cursor:
            cursor.execute(f'DROP DATABASE {cls.test_db};')

    def setUp(self):
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'bridge-test-only',
                               'DB_NAME': self.test_db, 'LAB2_DB_NAME': self.test_db})
        self.client = self.app.test_client()

    def token(self, response):
        return re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)

    def test_home_and_both_directions(self):
        home = self.client.get('/')
        self.assertEqual(home.status_code, 200)
        for url in ['/lab2/', '/library/']:
            self.assertIn(f'href="{url}"', home.get_data(as_text=True))
        for url in ['/lab2/login', '/lab2/register', '/library/']:
            page = self.client.get(url)
            self.assertEqual(page.status_code, 200)
            self.assertIn(b'Lab 2', page.data)
            self.assertIn(b'Lab 3', page.data)
        self.assertEqual(self.client.get('/lab2/', follow_redirects=True).status_code, 200)
        self.assertEqual(self.client.get('/lab2/static/style.css').status_code, 200)

    def test_login_and_tasks_survive_library_visit(self):
        form = self.client.get('/lab2/register')
        registered = self.client.post('/lab2/register', data={
            'csrf_token': self.token(form), 'name': 'Bridge Test',
            'email': 'bridge-test@example.test', 'password': 'test-password-123',
            'confirm_password': 'test-password-123',
        })
        self.assertEqual(registered.status_code, 302)
        self.assertEqual(registered.location, '/lab2/todos')
        tasks = self.client.get('/lab2/todos')
        added = self.client.post('/lab2/todos/add', data={
            'csrf_token': self.token(tasks), 'title': 'Switch labs and return',
        })
        self.assertEqual(added.status_code, 302)
        self.assertEqual(added.location, '/lab2/todos')
        self.assertEqual(self.client.get('/library/').status_code, 200)
        returned = self.client.get('/lab2/todos')
        self.assertEqual(returned.status_code, 200)
        self.assertIn(b'Switch labs and return', returned.data)
        self.assertIn(b'Bridge Test', returned.data)
        self.assertIn(b'/lab2/logout', returned.data)
        out = self.client.post('/lab2/logout', data={'csrf_token': self.token(returned)})
        self.assertEqual(out.location, '/lab2/login')
        self.assertEqual(self.client.get('/library/').status_code, 200)
        self.assertEqual(self.client.get('/lab2/todos').location, '/lab2/login')


if __name__ == '__main__':
    unittest.main()
