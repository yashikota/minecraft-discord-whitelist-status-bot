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
                    first_join_at TIMESTAMP NULL,
                    last_seen_at TIMESTAMP NULL,
                    total_playtime INTEGER DEFAULT 0,
                    is_online INTEGER DEFAULT 0
                )
            """)

            # Add new columns for existing installations
            cursor.execute("PRAGMA table_info(whitelist_users)")
            columns = [col[1] for col in cursor.fetchall()]

            if "first_join_at" not in columns:
                cursor.execute(
                    "ALTER TABLE whitelist_users ADD COLUMN first_join_at TIMESTAMP NULL"
                )
            if "last_seen_at" not in columns:
                cursor.execute(
                    "ALTER TABLE whitelist_users ADD COLUMN last_seen_at TIMESTAMP NULL"
                )
            if "total_playtime" not in columns:
                cursor.execute(
                    "ALTER TABLE whitelist_users ADD COLUMN total_playtime INTEGER DEFAULT 0"
                )

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
                # Update when player comes online
                cursor.execute(
                    """UPDATE whitelist_users
                    SET is_online = 1,
                        joined_at = datetime('now', 'utc'),
                        first_join_at = COALESCE(first_join_at, datetime('now', 'utc'))
                    WHERE minecraft_username = ?""",
                    (minecraft_username,),
                )
            else:
                # Update when player goes offline
                # Calculate and add session playtime
                cursor.execute(
                    """UPDATE whitelist_users
                    SET is_online = 0,
                        last_seen_at = datetime('now', 'utc'),
                        total_playtime = total_playtime +
                        CASE
                            WHEN joined_at IS NOT NULL
                            THEN (julianday('now', 'utc') - julianday(joined_at)) * 24 * 60 * 60
                            ELSE 0
                        END
                    WHERE minecraft_username = ?""",
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

    @safe_sync("Player stats retrieval", default_return=None)
    def get_player_stats(self, minecraft_username: str) -> dict | None:
        """Get player statistics including total playtime, first join, and last seen"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT
                    minecraft_username,
                    first_join_at,
                    last_seen_at,
                    total_playtime,
                    is_online,
                    joined_at,
                    created_at
                FROM whitelist_users
                WHERE minecraft_username = ?""",
                (minecraft_username,),
            )
            result = cursor.fetchone()

            if not result:
                return None

            (
                username,
                first_join,
                last_seen,
                total_playtime,
                is_online,
                joined_at,
                created_at,
            ) = result

            # Calculate current session time if player is online
            current_session_time = 0
            if is_online and joined_at:
                cursor.execute(
                    "SELECT (julianday('now', 'utc') - julianday(?)) * 24 * 60 * 60",
                    (joined_at,),
                )
                current_session_result = cursor.fetchone()
                if current_session_result:
                    current_session_time = int(current_session_result[0])

            return {
                "username": username,
                "first_join_at": first_join,
                "last_seen_at": last_seen,
                "total_playtime": total_playtime + current_session_time,
                "is_online": bool(is_online),
                "current_session_time": current_session_time,
                "created_at": created_at,
            }

    @safe_sync("All players stats retrieval", default_return=[])
    def get_all_players_stats(self) -> list[dict]:
        """Get statistics for all registered players"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT
                    minecraft_username,
                    first_join_at,
                    last_seen_at,
                    total_playtime,
                    is_online,
                    joined_at,
                    created_at
                FROM whitelist_users
                ORDER BY total_playtime DESC"""
            )
            results = cursor.fetchall()

            all_stats = []
            for result in results:
                (
                    username,
                    first_join,
                    last_seen,
                    total_playtime,
                    is_online,
                    joined_at,
                    created_at,
                ) = result

                # Calculate current session time if player is online
                current_session_time = 0
                if is_online and joined_at:
                    cursor.execute(
                        "SELECT (julianday('now', 'utc') - julianday(?)) * 24 * 60 * 60",
                        (joined_at,),
                    )
                    current_session_result = cursor.fetchone()
                    if current_session_result:
                        current_session_time = int(current_session_result[0])

                all_stats.append(
                    {
                        "username": username,
                        "first_join_at": first_join,
                        "last_seen_at": last_seen,
                        "total_playtime": total_playtime + current_session_time,
                        "is_online": bool(is_online),
                        "current_session_time": current_session_time,
                        "created_at": created_at,
                    }
                )

            return all_stats
