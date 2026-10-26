"""Run with: python website/app.py (from the project folder)."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from library import library
from lab2.app import create_app as create_lab2_app

load_dotenv(Path(__file__).with_name('.env'))


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY') or secrets.token_hex(32),
        DB_HOST=os.getenv('DB_HOST', '127.0.0.1'),
        DB_PORT=int(os.getenv('DB_PORT', '3306')),
        DB_USER=os.getenv('DB_USER', 'root'),
        DB_PASSWORD=os.getenv('DB_PASSWORD', ''),
        DB_NAME=os.getenv('DB_NAME', 'library_lab3_2304066'),
        LAB2_DB_NAME=os.getenv('LAB2_DB_NAME', 'registration'),
        UPLOAD_FOLDER=str(Path(__file__).parent / 'static' / 'uploads'),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        TEMPLATES_AUTO_RELOAD=True,
    )
    if test_config:
        app.config.update(test_config)
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    app.register_blueprint(library, url_prefix='/library')

    @app.route('/')
    def home():
        return render_template('labs.html')

    # Each lab keeps its own routes, templates, database and session cookie.
    # SCRIPT_NAME makes Lab 2's existing url_for links work under /lab2.
    lab2_app = create_lab2_app({
        'SECRET_KEY': app.config['SECRET_KEY'],
        'DB_HOST': app.config['DB_HOST'],
        'DB_PORT': app.config['DB_PORT'],
        'DB_USER': app.config['DB_USER'],
        'DB_PASSWORD': app.config['DB_PASSWORD'],
        'DB_NAME': app.config['LAB2_DB_NAME'],
        'SESSION_COOKIE_PATH': '/lab2',
        'TESTING': app.config.get('TESTING', False),
    })
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {'/lab2': lab2_app})
    app.extensions['lab2_app'] = lab2_app

    return app


app = create_app()

if __name__ == '__main__':
    # Local classroom app. Keep debug off so errors do not expose credentials.
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5003')), debug=False)
