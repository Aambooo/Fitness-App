# migration.py
from database_service import dbs

def convert_to_24hour():
    schedules = dbs.get_all_schedules()
    for s in schedules:
        if ' ' in s['time']:  # Contains AM/PM
            from datetime import datetime
            try:
                # Parse 12-hour time
                dt = datetime.strptime(s['time'], '%I:%M %p')
                # Convert to 24-hour format
                new_time = dt.strftime('%H:%M')
                # Update in database
                dbs.save_schedule(s['email'], {
                    'video_id': s['video_id'],
                    'time': new_time,
                    'title': s['title'],
                    'channel': s['channel'],
                    'duration': s['duration'],
                    'user_id': s['user_id']
                })
                print(f"Converted {s['time']} → {new_time}")
            except ValueError as e:
                print(f"Error converting {s['time']}: {e}")

if __name__ == "__main__":
    convert_to_24hour()