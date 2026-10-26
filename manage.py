"""Local helper. The actual DDL and seed SQL remain in the required .sql files."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

from dotenv import dotenv_values
import pymysql

ROOT = Path(__file__).resolve().parent
CONFIG = dotenv_values(ROOT / 'website' / '.env')
DATABASE = 'library_lab3_2304066'


def connection():
    return pymysql.connect(
        host=CONFIG.get('DB_HOST', '127.0.0.1'),
        port=int(CONFIG.get('DB_PORT', '3306')),
        user=CONFIG.get('DB_USER', 'root'),
        password=CONFIG.get('DB_PASSWORD', ''), connect_timeout=5,
    )


def mysql_client():
    executable = shutil.which('mysql')
    if not executable:
        bundled = Path('/opt/homebrew/opt/mysql@8.4/bin/mysql')
        if bundled.exists():
            executable = str(bundled)
    if not executable:
        raise RuntimeError('MySQL client not found. Add the mysql executable to PATH.')
    return executable


def build():
    # Use the MySQL client exactly as requested in the lab handout.
    environment = os.environ.copy()
    environment['MYSQL_PWD'] = CONFIG.get('DB_PASSWORD', '')
    command = [mysql_client(), '-h', CONFIG.get('DB_HOST', '127.0.0.1'),
               '-P', CONFIG.get('DB_PORT', '3306'), '-u', CONFIG.get('DB_USER', 'root')]
    for filename in ('problem2_DDL.sql', 'problem2_DML.sql'):
        with (ROOT / filename).open('rb') as script:
            subprocess.run(command, stdin=script, env=environment, check=True)
        print('Executed:', filename)


def check():
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(f'USE {DATABASE};')
        cursor.execute('SELECT author_id, name, country FROM AUTHOR;')
        authors = cursor.fetchall()
        cursor.execute('SELECT book_id, title, price, author_id FROM BOOK;')
        books = cursor.fetchall()
        print('Database:', DATABASE)
        print('Authors:', len(authors), '| Books:', len(books))
        for row in authors:
            print('AUTHOR', row)
        for row in books:
            print('BOOK', row)


def main():
    mode = sys.argv[1] if len(sys.argv) == 2 else 'help'
    if mode in {'init', 'reset'}:
        if not (ROOT / 'website' / '.env').is_file():
            raise RuntimeError('Create website/.env from .env.example before setup.')
        if CONFIG.get('DB_NAME') != DATABASE:
            raise RuntimeError(f'This helper only manages {DATABASE}. Check DB_NAME.')
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute('SHOW DATABASES;')
            exists = DATABASE in [row[0] for row in cursor.fetchall()]
        if exists and mode == 'init':
            raise RuntimeError('Assignment database already exists. Use check, or reset intentionally.')
        if mode == 'reset':
            answer = input('Reset all library records and uploaded images? Type RESET: ')
            if answer != 'RESET':
                print('Cancelled. Nothing changed.')
                return
        build()
        uploads = ROOT / 'website' / 'static' / 'uploads'
        for pattern in ('book-*.png', 'author-*.png'):
            for image in uploads.glob(pattern):
                image.unlink()
        check()
    elif mode == 'check':
        check()
    elif mode == 'run':
        subprocess.run([sys.executable, str(ROOT / 'website' / 'app.py')], cwd=ROOT, check=True)
    else:
        print('Usage: python manage.py init|check|run|reset')
        print('init: create a NEW assignment database; refuses to replace an existing one.')
        print('reset: restore 3 authors / 6 books and remove uploads after confirmation.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, pymysql.MySQLError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, pymysql.MySQLError):
            print('Database error code:', exc.args[0], '- check website/.env and MySQL.')
        else:
            print(str(exc))
        sys.exit(1)
