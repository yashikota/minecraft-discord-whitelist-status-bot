import inspect
import logging
from datetime import datetime
from functools import wraps

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)


def get_caller_logger() -> logging.Logger:
    """Get logger for the calling module"""
    frame = inspect.currentframe()
    try:
        caller_frame = frame.f_back.f_back
        module_name = caller_frame.f_globals.get("__name__", "unknown")
        return logging.getLogger(module_name)
    finally:
        del frame


def log_info(operation: str, message: str) -> None:
    """Standardized info logging"""
    logger = get_caller_logger()
    logger.info(f"{operation}: {message}")


def log_error(operation: str, error: Exception) -> None:
    """Standardized error logging"""
    logger = get_caller_logger()
    logger.error(f"{operation} error: {error}")


def safe_async(operation_name: str):
    """Decorator for safe async operations with standardized error handling"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_error(operation_name, e)
                return None

        return wrapper

    return decorator


def safe_sync(operation_name: str, default_return=None):
    """Decorator for safe sync operations with standardized error handling"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_error(operation_name, e)
                return default_return

        return wrapper

    return decorator


class ErrorMessages:
    """Standard error messages for the bot"""

    ADMIN_ONLY = "❌ This command can only be used by administrators."
    GENERIC_ERROR = "❌ An error occurred. Please contact an administrator."
    SERVER_OFFLINE = "❌ Server is offline."
    PROCESSING_REQUEST = "⏳ Already processing. Please wait."
    USER_NOT_FOUND = "❌ User not found."
    DATABASE_ERROR = "❌ Database operation failed."
    SERVER_CONNECTION_ERROR = "❌ Failed to connect to Minecraft server."


def format_success_message(action: str, details: str = "") -> str:
    """Format success messages consistently"""
    return f"✅ {action}" + (f" {details}" if details else "")


def format_warning_message(message: str) -> str:
    """Format warning messages consistently"""
    return f"⚠️ {message}"


def format_error_message(message: str) -> str:
    """Format error messages consistently"""
    return f"❌ {message}"


def get_current_timestamp() -> str:
    """Get current timestamp in consistent format"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format (hours:minutes:seconds)"""
    if seconds < 0:
        return "0:00:00"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    return f"{hours}:{minutes:02d}:{seconds:02d}"


def format_datetime(datetime_str: str | None) -> str:
    """Format datetime string for display"""
    if not datetime_str:
        return "Not recorded"

    try:
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return "Invalid date"
