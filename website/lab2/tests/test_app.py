import re
import sqlite3
import unittest
from datetime import datetime
from unittest.mock import patch

import bcrypt
import pymysql
from cachelib import SimpleCache

from app import create_app


class CursorAdapter:
    def __init__(self, connection):
        self.cursor = connection.cursor()
        self.lastrowid = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()

    def execute(self, sql, values):
        try:
            self.cursor.execute(sql.replace("%s", "?"), values)
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error):
                raise pymysql.IntegrityError(1062, "Duplicate entry") from error
            raise
        self.lastrowid = self.cursor.lastrowid
        return self.cursor.rowcount

    def fetchall(self):
        rows = []
        for row in self.cursor.fetchall():
            item = dict(row)
            if "created_at" in item:
                item["created_at"] = datetime.fromisoformat(item["created_at"])
            rows.append(item)
        return rows


class ConnectionAdapter:
    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return CursorAdapter(self.connection)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        pass


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE todos (
                todo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(user_id),
                title TEXT NOT NULL,
                is_done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.connect = patch("app.pymysql.connect", return_value=ConnectionAdapter(self.db)).start()
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "automated-test-key-not-for-real-use",
            "SESSION_CACHELIB": SimpleCache(),
        })
        self.client = self.app.test_client()

    def tearDown(self):
        patch.stopall()
        self.db.close()

    def token(self, client):
        with client.session_transaction() as session:
            return session["csrf_token"]

    def post(self, client, url, **data):
        data["csrf_token"] = self.token(client)
        return client.post(url, data=data)

    def register(self, client=None, email="jana@example.com", name="Jana"):
        client = client or self.client
        client.get("/register")
        return self.post(client, "/register", name=name, email=email,
                         password="sample-password", confirm_password="sample-password")

    def test_private_routes_require_login(self):
        for url in ["/todos", "/todos/add", "/todos/1/edit", "/todos/1/toggle", "/todos/1/delete"]:
            response = self.client.get(url) if url == "/todos" else self.client.post(url)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith("/login"))

    def test_empty_registration_and_login_do_not_open_database(self):
        self.client.get("/register")
        response = self.post(self.client, "/register")
        self.assertEqual(response.status_code, 400)
        for message in ["Name is required", "Email is required", "Password is required", "Confirm password is required"]:
            self.assertIn(message, response.text)
        self.assertFalse(self.connect.called)
        self.client.get("/login")
        response = self.post(self.client, "/login")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Email is required", response.text)
        self.assertIn("Password is required", response.text)
        self.assertFalse(self.connect.called)

    def test_password_mismatch_and_bcrypt_limit(self):
        self.client.get("/register")
        response = self.post(self.client, "/register", name="Jana", email="j@example.com", password="one", confirm_password="two")
        self.assertIn("Passwords do not match", response.text)
        response = self.post(self.client, "/register", name="Jana", email="j@example.com", password="x" * 73, confirm_password="x" * 73)
        self.assertIn("Password is too long", response.text)
        self.assertFalse(self.connect.called)

    def test_registration_hash_session_and_duplicate_email(self):
        response = self.register()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/todos"))
        user = self.db.execute("SELECT * FROM users").fetchone()
        self.assertNotEqual(user["password_hash"], "sample-password")
        self.assertTrue(bcrypt.checkpw(b"sample-password", user["password_hash"].encode()))
        with self.client.session_transaction() as session:
            self.assertEqual(session["user_id"], user["user_id"])
        other = self.app.test_client()
        response = self.register(other, email="JANA@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Email Already Exists", response.text)
        self.assertEqual(self.db.execute("SELECT count(*) FROM users").fetchone()[0], 1)

    def test_login_errors_injection_and_success(self):
        self.register()
        self.post(self.client, "/logout")
        self.client.get("/login")
        for email, password in [("unknown@example.com", "sample-password"), ("jana@example.com", "wrong"), ("' OR '1'='1' --", "anything")]:
            response = self.post(self.client, "/login", email=email, password=password)
            self.assertEqual(response.status_code, 400)
            self.assertIn("Invalid email or password", response.text)
            with self.client.session_transaction() as session:
                self.assertNotIn("user_id", session)
        response = self.post(self.client, "/login", email="jana@example.com", password="sample-password")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/todos"))

    def test_logout_invalidates_old_cookie(self):
        self.register()
        cookie_name = self.app.config["SESSION_COOKIE_NAME"]
        old_cookie = self.client.get_cookie(cookie_name).value
        self.post(self.client, "/logout")
        replay = self.app.test_client()
        replay.set_cookie(cookie_name, old_cookie)
        response = replay.get("/todos")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/login"))

    def test_crud_order_open_count_and_delete_confirmation(self):
        self.register()
        self.post(self.client, "/todos/add", title="First task")
        self.post(self.client, "/todos/add", title="Second task")
        page = self.client.get("/todos").text
        self.assertLess(page.index('value="Second task"'), page.index('value="First task"'))
        self.assertIn("<strong>2</strong>", page)
        self.post(self.client, "/todos/1/edit", title="Revised task")
        self.post(self.client, "/todos/1/toggle", is_done="1")
        row = self.db.execute("SELECT * FROM todos WHERE todo_id=1").fetchone()
        self.assertEqual(row["title"], "Revised task")
        self.assertEqual(row["is_done"], 1)
        self.assertIn("<strong>1</strong>", self.client.get("/todos").text)
        self.post(self.client, "/todos/1/toggle", is_done="0")
        self.assertEqual(self.db.execute("SELECT is_done FROM todos WHERE todo_id=1").fetchone()[0], 0)
        response = self.post(self.client, "/todos/1/delete")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.execute("SELECT count(*) FROM todos").fetchone()[0], 2)
        self.post(self.client, "/todos/1/delete", confirm_delete="yes")
        self.assertEqual(self.db.execute("SELECT count(*) FROM todos").fetchone()[0], 1)

    def test_invalid_titles_do_not_change_data(self):
        self.register()
        self.post(self.client, "/todos/add", title="Keep me")
        for title, message in [("   ", "Title is required"), ("x" * 201, "Title is too long (200 characters at most)")]:
            for url in ["/todos/add", "/todos/1/edit"]:
                response = self.post(self.client, url, title=title)
                self.assertEqual(response.status_code, 400)
                self.assertIn(message, response.text)
                rows = self.db.execute("SELECT title FROM todos").fetchall()
                self.assertEqual([row[0] for row in rows], ["Keep me"])
        response = self.post(self.client, "/todos/1/toggle", is_done="7")
        self.assertEqual(response.status_code, 400)

    def test_two_user_isolation_and_forged_user_id(self):
        self.register()
        self.post(self.client, "/todos/add", title="Private Jana task")
        other = self.app.test_client()
        self.register(other, email="omar@example.com", name="Omar")
        self.assertNotIn("Private Jana task", other.get("/todos").text)
        self.post(other, "/todos/1/edit", title="Stolen", user_id="1")
        self.post(other, "/todos/1/toggle", is_done="1", user_id="1")
        self.post(other, "/todos/1/delete", confirm_delete="yes", user_id="1")
        row = self.db.execute("SELECT * FROM todos WHERE todo_id=1").fetchone()
        self.assertEqual(row["title"], "Private Jana task")
        self.assertEqual(row["is_done"], 0)
        self.post(other, "/todos/add", title="Omar task", user_id="1")
        self.assertEqual(self.db.execute("SELECT user_id FROM todos WHERE todo_id=2").fetchone()[0], 2)

    def test_html_is_escaped(self):
        self.register(name="<script>alert(1)</script>")
        self.post(self.client, "/todos/add", title='<img src=x onerror="alert(1)">')
        page = self.client.get("/todos").text
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("&lt;img", page)

    def test_csrf_rejection_and_missing_page_are_styled(self):
        response = self.client.post("/register", data={"name": "Jana"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("This form has expired", response.text)
        self.assertIn("style.css", response.text)
        response = self.client.get("/missing-page")
        self.assertEqual(response.status_code, 404)
        self.assertIn("style.css", response.text)
        self.assertFalse(self.connect.called)

    def test_database_failure_is_friendly(self):
        self.client.get("/login")
        self.connect.side_effect = pymysql.OperationalError(2003, "Cannot connect")
        response = self.post(self.client, "/login", email="jana@example.com", password="test")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Database unavailable", response.text)
        self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
