import os
import mysql.connector


def get_connection():
    """Open a connection to Store 1 (the app's persistent MySQL database).
    Credentials come from the process environment (see .env), never read
    directly from a file here."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "patient_db"),
    )
