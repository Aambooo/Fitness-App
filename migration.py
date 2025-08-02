"""
Database migration utility for time format conversion
Converts 12-hour (AM/PM) schedules to 24-hour format
"""

from database_service import dbs
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def convert_to_24hour() -> dict:
    """
    Convert all schedule times from 12-hour to 24-hour format
    Returns:
        dict: Conversion statistics {
            'total': int,
            'converted': int,
            'failed': int,
            'unchanged': int
        }
    """
    stats = {'total': 0, 'converted': 0, 'failed': 0, 'unchanged': 0}
    
    try:
        schedules = dbs.get_all_schedules()
        stats['total'] = len(schedules)
        
        if not schedules:
            logging.info("No schedules found in database")
            return stats

        for s in schedules:
            if not s.get('time'):
                stats['unchanged'] += 1
                continue
                
            # Skip if already in 24-hour format (HH:MM)
            if ' ' not in s['time'] and ':' in s['time']:
                stats['unchanged'] += 1
                continue

            try:
                # Parse 12-hour time (with AM/PM)
                dt = datetime.strptime(s['time'], '%I:%M %p')
                new_time = dt.strftime('%H:%M')
                
                # Update in database
                success = dbs.save_schedule(s['email'], {
                    'video_id': s['video_id'],
                    'time': new_time,
                    'title': s['title'],
                    'channel': s['channel'],
                    'duration': s['duration'],
                    'user_id': s['user_id']
                })
                
                if success:
                    stats['converted'] += 1
                    logging.info(f"Converted {s['time']} → {new_time}")
                else:
                    stats['failed'] += 1
                    logging.error(f"Failed to update {s['email']}")
                    
            except ValueError as e:
                stats['failed'] += 1
                logging.error(f"Error converting {s['time']}: {str(e)}")
                
        return stats
        
    except Exception as e:
        logging.critical(f"Migration failed: {str(e)}")
        return stats

if __name__ == "__main__":
    print("Starting time format migration...")
    results = convert_to_24hour()
    print("\nMigration Results:")
    print(f"Total schedules: {results['total']}")
    print(f"Successfully converted: {results['converted']}")
    print(f"Failed conversions: {results['failed']}")
    print(f"Already in 24-hour format: {results['unchanged']}")