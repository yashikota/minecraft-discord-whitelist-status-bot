import sqlite3


class DatabaseManager:
    def __init__(self, db_path: str = "whitelist.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS whitelist_users (
                        discord_id INTEGER PRIMARY KEY,
                        minecraft_username TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                print("Database initialized successfully")
        except Exception as e:
            print(f"Database initialization error: {e}")

    def add_user(self, discord_id: int, minecraft_username: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO whitelist_users (discord_id, minecraft_username) VALUES (?, ?)",
                    (discord_id, minecraft_username),
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"User addition error: {e}")
            return False

    def get_user(self, discord_id: int) -> str | None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT minecraft_username FROM whitelist_users WHERE discord_id = ?",
                    (discord_id,),
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"User retrieval error: {e}")
            return None

    def remove_user(self, discord_id: int) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM whitelist_users WHERE discord_id = ?", (discord_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"User deletion error: {e}")
            return False

    def get_all_users(self) -> list[tuple[int, str]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT discord_id, minecraft_username FROM whitelist_users"
                )
                return cursor.fetchall()
        except Exception as e:
            print(f"All users retrieval error: {e}")
            return []
