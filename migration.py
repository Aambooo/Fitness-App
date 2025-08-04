"""
Database migration utility for time format conversion
Enhanced with transaction support and better error recovery
"""

from database_service import dbs
from datetime import datetime
import logging
from typing import Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("migration.log", mode="a"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


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
    """
    Migrate all schedules to 24-hour format with transaction support
    Returns conversion statistics
    """
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
                    """
                    UPDATE schedule 
                    SET time = %s
                    WHERE email = %s AND video_id = %s
                """,
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


def print_results(stats: Dict) -> None:
    """Display migration results in readable format"""
    print("\nMigration Report")
    print("=" * 40)
    print(f"{'Total schedules:':<25} {stats['total']}")
    print(f"{'Successfully converted:':<25} {stats['converted']}")
    print(f"{'Already in 24h format:':<25} {stats['unchanged']}")
    print(f"{'Failed conversions:':<25} {stats['failed']}")
    print(f"{'Invalid time formats:':<25} {stats.get('invalid', 0)}")
    print("\nDetailed log saved to migration.log")


if __name__ == "__main__":
    logger.info("Starting time format migration")
    results = migrate_schedules()
    print_results(results)
    logger.info("Migration completed")
