"""
Database Migration Utility
Handles both time format conversion and schema migrations
"""

from database_service import dbs
from datetime import datetime
import logging
from typing import Dict, List, Tuple
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("migration.log", mode="a"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# ====================== Time Format Migration ======================
def get_all_schedules() -> List[Dict]:
    """Safe wrapper to get all schedules with error handling"""
    try:
        return dbs.get_all_schedules() or []
    except Exception as e:
        logger.error(f"Failed to fetch schedules: {str(e)}")
        return []


def convert_time_format(time_str: str) -> str:
    """Convert 12-hour format to 24-hour format with validation"""
    try:
        if not time_str or ":" not in time_str:
            return time_str

        if " " in time_str:  # Contains AM/PM
            dt = datetime.strptime(time_str, "%I:%M %p")
            return dt.strftime("%H:%M")
        return time_str  # Already in 24-hour format
    except ValueError as e:
        logger.error(f"Time format conversion failed for '{time_str}': {str(e)}")
        return time_str


def migrate_schedules() -> Dict[str, int]:
    """Migrate all schedules to 24-hour format with transaction support"""
    stats = {"total": 0, "converted": 0, "failed": 0, "unchanged": 0, "invalid": 0}

    try:
        schedules = get_all_schedules()
        stats["total"] = len(schedules)

        if not schedules:
            logger.info("No schedules found for migration")
            return stats

        conn = dbs.get_connection()
        cursor = conn.cursor()

        for schedule in schedules:
            original_time = schedule.get("time", "")
            new_time = convert_time_format(original_time)

            if not new_time or new_time == original_time:
                stats["unchanged"] += 1
                continue

            try:
                cursor.execute(
                    """UPDATE schedule SET time = %s
                    WHERE email = %s AND video_id = %s""",
                    (new_time, schedule["email"], schedule["video_id"]),
                )
                stats["converted"] += 1
                logger.info(
                    f"Converted {schedule['email']}: {original_time} → {new_time}"
                )
            except Exception as e:
                conn.rollback()
                stats["failed"] += 1
                logger.error(f"Failed to update {schedule['email']}: {str(e)}")

        conn.commit()
        return stats

    except Exception as e:
        logger.critical(f"Migration aborted: {str(e)}")
        if "conn" in locals():
            conn.rollback()
        return stats
    finally:
        if "conn" in locals():
            conn.close()


# ====================== Schema Migrations ======================
def add_verification_column() -> Tuple[bool, str]:
    """Add is_verified column to users table if it doesn't exist"""
    conn = None
    try:
        conn = dbs.get_connection()
        cursor = conn.cursor()

        # Check if column exists
        cursor.execute(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'is_verified'
        """
        )
        if cursor.fetchone()[0] > 0:
            return True, "Column already exists"

        # Add the column
        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN is_verified BOOLEAN DEFAULT FALSE
        """
        )
        conn.commit()
        return True, "Added is_verified column"

    except Exception as e:
        logger.error(f"Failed to add column: {str(e)}")
        if conn:
            conn.rollback()
        return False, str(e)
    finally:
        if conn:
            conn.close()


# ====================== Migration Runner ======================
def run_migrations() -> Dict[str, Dict]:
    """Execute all pending migrations"""
    results = {}

    # Schema migrations
    results["schema"] = {"add_verification_column": add_verification_column()}

    # Data migrations
    results["time_conversion"] = migrate_schedules()

    return results


def print_results(results: Dict) -> None:
    """Display all migration results"""
    print("\n=== Migration Results ===")

    # Schema migration results
    print("\nSchema Migrations:")
    for name, (success, message) in results["schema"].items():
        status = "✓" if success else "✗"
        print(f"{status} {name}: {message}")

    # Time conversion results
    stats = results["time_conversion"]
    print("\nTime Format Conversions:")
    print(f"Total schedules: {stats['total']}")
    print(f"Converted: {stats['converted']}")
    print(f"Unchanged: {stats['unchanged']}")
    print(f"Failed: {stats['failed']}")
    print(f"Invalid: {stats.get('invalid', 0)}")


if __name__ == "__main__":
    logger.info("Starting database migrations")
    try:
        results = run_migrations()
        print_results(results)
        logger.info("All migrations completed")
    except Exception as e:
        logger.critical(f"Migration failed: {str(e)}")
        sys.exit(1)
