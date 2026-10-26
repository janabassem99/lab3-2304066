import os
import secrets
from datetime import timedelta
from functools import wraps
from pathlib import Path

import bcrypt
import pymysql
from cachelib.file import FileSystemCache
from dotenv import dotenv_values
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from flask_session import Session
from werkzeug.exceptions import HTTPException

BASE_DIR = Path(__file__).resolve().parent
LOCAL_CONFIG = dotenv_values(BASE_DIR.parent / ".env")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=LOCAL_CONFIG.get("SECRET_KEY"),
        DB_HOST=LOCAL_CONFIG.get("DB_HOST", "127.0.0.1"),
        DB_PORT=int(LOCAL_CONFIG.get("DB_PORT", "3306")),
        DB_USER=LOCAL_CONFIG.get("DB_USER", "root"),
        DB_PASSWORD=LOCAL_CONFIG.get("DB_PASSWORD", ""),
        DB_NAME=LOCAL_CONFIG.get("LAB2_DB_NAME", "registration"),
        SESSION_COOKIE_NAME="lab2_session",
        TEMPLATES_AUTO_RELOAD=True,
        SESSION_TYPE="cachelib",
        SESSION_PERMANENT=False,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"] or app.config["SECRET_KEY"] == "replace_with_a_generated_secret":
        raise RuntimeError("Set SECRET_KEY in your .env file before starting the application.")
    if "SESSION_CACHELIB" not in app.config:
        session_dir = BASE_DIR / "instance" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        app.config["SESSION_CACHELIB"] = FileSystemCache(str(session_dir), threshold=500)
    Session(app)

    def get_db():
        if "db" not in g:
            g.db = pymysql.connect(
                host=app.config["DB_HOST"],
                port=int(app.config["DB_PORT"]),
                user=app.config["DB_USER"],
                password=app.config["DB_PASSWORD"],
                database=app.config["DB_NAME"],
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=5,
            )
        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    def select_rows(sql, values):
        with get_db().cursor() as cursor:
            cursor.execute(sql, values)
            return cursor.fetchall()

    def change_rows(sql, values):
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                count = cursor.execute(sql, values)
                new_id = cursor.lastrowid
            connection.commit()
            return count, new_id
        except pymysql.MySQLError:
            connection.rollback()
            raise

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    @app.context_processor
    def template_helpers():
        return {"csrf_token": csrf_token}

    @app.before_request
    def protect_forms():
        private_endpoints = {"todos", "add_todo", "edit_todo", "toggle_todo", "delete_todo", "logout"}
        if request.endpoint in private_endpoints and "user_id" not in session:
            return redirect(url_for("login"))
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            supplied = request.form.get("csrf_token", "")
            if not expected or not secrets.compare_digest(expected, supplied):
                abort(400, description="This form has expired. Reload the page and try again.")

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    def start_session(user_id, name):
        session.clear()
        session["user_id"] = user_id
        session["name"] = name
        app.session_interface.regenerate(session)
        csrf_token()

    def title_error(title):
        if not title:
            return "Title is required"
        if len(title) > 200:
            return "Title is too long (200 characters at most)"
        return ""

    def show_todos(errors=None, add_title="", edit_id=None, edit_title="", status=200):
        items = select_rows(
            "SELECT todo_id, title, is_done, created_at FROM todos WHERE user_id = %s ORDER BY todo_id DESC;",
            (session["user_id"],),
        )
        return render_template(
            "todos.html", todos=items,
            open_count=sum(1 for item in items if not item["is_done"]),
            errors=errors or {}, add_title=add_title, edit_id=edit_id, edit_title=edit_title,
        ), status

    @app.route("/")
    def home():
        return redirect(url_for("todos" if "user_id" in session else "login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if "user_id" in session:
            return redirect(url_for("todos"))
        errors = {}
        values = {"name": "", "email": ""}
        if request.method == "POST":
            values["name"] = request.form.get("name", "").strip()
            values["email"] = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirmation = request.form.get("confirm_password", "")
            if not values["name"]:
                errors["name"] = "Name is required"
            elif len(values["name"]) > 100:
                errors["name"] = "Name is too long (100 characters at most)"
            if not values["email"]:
                errors["email"] = "Email is required"
            elif len(values["email"]) > 255:
                errors["email"] = "Email is too long (255 characters at most)"
            if not password:
                errors["password"] = "Password is required"
            elif len(password.encode("utf-8")) > 72:
                errors["password"] = "Password is too long (72 UTF-8 bytes at most)"
            if not confirmation:
                errors["confirm_password"] = "Confirm password is required"
            elif password and password != confirmation:
                errors["confirm_password"] = "Passwords do not match"
            if not errors:
                password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
                try:
                    _, user_id = change_rows(
                        "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s);",
                        (values["email"], values["name"], password_hash),
                    )
                except pymysql.IntegrityError as error:
                    if error.args[0] != 1062:
                        raise
                    errors["email"] = "Email Already Exists"
                else:
                    start_session(user_id, values["name"])
                    flash("Your account is ready. Add your first task!", "success")
                    return redirect(url_for("todos"))
        return render_template("register.html", errors=errors, values=values), 400 if errors else 200

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if "user_id" in session:
            return redirect(url_for("todos"))
        errors = {}
        email = ""
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not email:
                errors["email"] = "Email is required"
            if not password:
                errors["password"] = "Password is required"
            if not errors:
                users = select_rows(
                    "SELECT user_id, name, password_hash FROM users WHERE email = %s;", (email,),
                )
                user = users[0] if users else None
                valid = False
                if user and len(password.encode("utf-8")) <= 72:
                    try:
                        valid = bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8"))
                    except ValueError:
                        valid = False
                if valid:
                    start_session(user["user_id"], user["name"])
                    return redirect(url_for("todos"))
                errors["form"] = "Invalid email or password"
        return render_template("login.html", errors=errors, email=email), 400 if errors else 200

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/todos")
    @login_required
    def todos():
        return show_todos()

    @app.post("/todos/add")
    @login_required
    def add_todo():
        title = request.form.get("title", "").strip()
        error = title_error(title)
        if error:
            return show_todos(errors={"add": error}, add_title=title, status=400)
        change_rows("INSERT INTO todos (user_id, title) VALUES (%s, %s);", (session["user_id"], title))
        flash("Task added.", "success")
        return redirect(url_for("todos"))

    @app.post("/todos/<int:todo_id>/edit")
    @login_required
    def edit_todo(todo_id):
        title = request.form.get("title", "").strip()
        error = title_error(title)
        if error:
            return show_todos(errors={"edit": error}, edit_id=todo_id, edit_title=title, status=400)
        count, _ = change_rows(
            "UPDATE todos SET title = %s WHERE todo_id = %s AND user_id = %s;",
            (title, todo_id, session["user_id"]),
        )
        flash("Task saved." if count else "No changes made.", "success" if count else "info")
        return redirect(url_for("todos"))

    @app.post("/todos/<int:todo_id>/toggle")
    @login_required
    def toggle_todo(todo_id):
        value = request.form.get("is_done", "")
        if value not in {"0", "1"}:
            abort(400, description="Choose a valid task status.")
        count, _ = change_rows(
            "UPDATE todos SET is_done = %s WHERE todo_id = %s AND user_id = %s;",
            (int(value), todo_id, session["user_id"]),
        )
        flash("Task status updated." if count else "No changes made.", "success" if count else "info")
        return redirect(url_for("todos"))

    @app.post("/todos/<int:todo_id>/delete")
    @login_required
    def delete_todo(todo_id):
        if request.form.get("confirm_delete") != "yes":
            abort(400, description="Please confirm before deleting a task.")
        count, _ = change_rows(
            "DELETE FROM todos WHERE todo_id = %s AND user_id = %s;", (todo_id, session["user_id"]),
        )
        flash("Task deleted." if count else "Task was not found in your list.", "success" if count else "info")
        return redirect(url_for("todos"))

    @app.errorhandler(pymysql.MySQLError)
    def database_error(error):
        app.logger.error("Database operation failed (%s).", type(error).__name__)
        return render_template("error.html", heading="Database unavailable", message="We could not complete your request. Please try again shortly."), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        return render_template("error.html", heading=error.name, message=error.description), error.code

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("error.html", heading="Something went wrong", message="Please return to the application and try again."), 500

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5001)
