# Farm2Home

Farm2Home is a Flask-based farming marketplace web application.

## Technology
- Python / Flask
- MySQL or MariaDB
- HTML, CSS, JavaScript

## Deploy notes
This project requires an externally hosted MySQL/MariaDB database. Create a database and import `schema.sql`, then configure these environment variables in your hosting provider:

- `SECRET_KEY`
- `DB_HOST`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`

Install dependencies with `pip install -r requirements.txt` and start with `gunicorn app:app`.

Do not commit real passwords, `.env` files, or database backups to a public repository.
