import sqlite3

from utils import log_info, safe_sync


class DatabaseManager:
    def __init__(self, db_path: str = "whitelist.db"):
        self.db_path = db_path
        self.init_database()

    @safe_sync("Database initialization")
    def init_database(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whitelist_users (
                    discord_id INTEGER PRIMARY KEY,
                    minecraft_username TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'utc')),
                    joined_at TIMESTAMP NULL,
                    is_online INTEGER DEFAULT 0
                )
            """)

            conn.commit()
            log_info("Database initialization", "Initialized successfully")

    @safe_sync("User addition", default_return=False)
    def add_user(self, discord_id: int, minecraft_username: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO whitelist_users (discord_id, minecraft_username) VALUES (?, ?)",
                (discord_id, minecraft_username),
            )
            conn.commit()
            return True

    @safe_sync("User retrieval", default_return=None)
    def get_user(self, discord_id: int) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT minecraft_username FROM whitelist_users WHERE discord_id = ?",
                (discord_id,),
            )
            result = cursor.fetchone()
            return result[0] if result else None

    @safe_sync("User deletion", default_return=False)
    def remove_user(self, discord_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM whitelist_users WHERE discord_id = ?", (discord_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    @safe_sync("All users retrieval", default_return=[])
    def get_all_users(self) -> list[tuple[int, str, str, str, int]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT discord_id, minecraft_username, created_at, joined_at, is_online FROM whitelist_users"
            )
            return cursor.fetchall()

    @safe_sync("Player status update", default_return=False)
    def update_player_online_status(
        self, minecraft_username: str, is_online: bool
    ) -> bool:
        """Update player's online status and joined_at timestamp if coming online"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if is_online:
                cursor.execute(
                    "UPDATE whitelist_users SET is_online = 1, joined_at = datetime('now', 'utc') WHERE minecraft_username = ?",
                    (minecraft_username,),
                )
            else:
                cursor.execute(
                    "UPDATE whitelist_users SET is_online = 0 WHERE minecraft_username = ?",
                    (minecraft_username,),
                )

            conn.commit()
            return cursor.rowcount > 0

    @safe_sync("Online players retrieval", default_return=[])
    def get_online_players(self) -> list[tuple[int, str, str]]:
        """Get all currently online registered players with their join times"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT discord_id, minecraft_username, joined_at FROM whitelist_users WHERE is_online = 1"
            )
            return cursor.fetchall()
