
from sqlalchemy import text

from app.db.session import engine

try:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT DATABASE(), VERSION()")
        )
        database_name, mysql_version = result.one()

        print(f"Database: {database_name}")
        print(f"MySQL version: {mysql_version}")
        print("Database connection successful!")

except Exception as exc:
    print(f"Database connection failed: {exc}")
    raise
