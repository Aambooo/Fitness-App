import harperdb

# Configure HarperDB
url = "http://localhost:9925"  
username = "Nabin"
password = "Projectkolagi369$"

db = harperdb.HarperDB(
    url=url,
    username=username,
    password=password
)

SCHEMA = "workout_repo"
TABLE = "workouts"
TABLE_TODAY = "workout_today"
SCHEDULE_TABLE = "schedule"

# Workout Functions
def insert_workout(workout_data):
    return db.insert(SCHEMA, TABLE, [workout_data])

def delete_workout(video_id):
    return db.delete(SCHEMA, TABLE, [video_id])

def get_all_workouts():
    return db.sql(f"SELECT * FROM {SCHEMA}.{TABLE}")

def get_workout_by_id(video_id):
    return db.sql(f"SELECT * FROM {SCHEMA}.{TABLE} WHERE video_id = '{video_id}'")

def get_workout_today():
    return db.sql(f"SELECT * FROM {SCHEMA}.{TABLE_TODAY} WHERE id = 0")

def update_workout_today(workout_data, insert=False):
    workout_data['id'] = 0  # Unique ID for today's workout
    if insert:
        return db.insert(SCHEMA, TABLE_TODAY, [workout_data])
    return db.update(SCHEMA, TABLE_TODAY, [workout_data])

# Email Scheduling Functions
def insert_schedule(data):
    return db.insert(SCHEMA, SCHEDULE_TABLE, [data])

def get_schedules_by_time(time_str):
    return db.sql(f"SELECT * FROM {SCHEMA}.{SCHEDULE_TABLE} WHERE time = '{time_str}'")
# Add to database_service.py

def get_schedule_by_email(email):
    """Get existing schedule for an email"""
    return db.sql(f"SELECT * FROM {SCHEMA}.{SCHEDULE_TABLE} WHERE email = '{email}'")

def update_schedule(email, new_time, new_video_id):
    """Update existing schedule"""
    return db.update(
        SCHEMA,
        SCHEDULE_TABLE,
        [{
            "email": email,
            "time": new_time,
            "video_id": new_video_id
        }]
    )