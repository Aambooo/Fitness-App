import harperdb

url = "http://localhost:9925"
username = "Nabin"
password = "Projectkolagi369$"

db = harperdb.HarperDB(
    url = url,
    username = username ,
    password = password

)

SCHEMA = "workout_repo"
TABLE = "workouts"
TABLE_TODAY = "workout_today"
TABLE_ALERTS = "workout_alerts"


def insert_workout(workout_data):
    if not isinstance(workout_data, dict):
        print("Workout data is invalid:", workout_data)
        return
    return db.insert(SCHEMA,TABLE,[workout_data])

def delete_workout(workout_id):
    return db.delete(SCHEMA,TABLE,[workout_id])

def get_all_workouts():
    return db.sql(f"select video_id,channel,title,duration from {SCHEMA}.{TABLE}")

def get_workout_today():
    return db.sql(f"select * from {SCHEMA}.{TABLE_TODAY} where id = 0")

def update_workout_today(workout_data, insert=False):
    workout_data['id'] = 0
    if insert:
        return db.insert(SCHEMA, TABLE_TODAY,[workout_data])
    return db.update(SCHEMA,TABLE_TODAY,[workout_data])

SCHEDULE_TABLE = "schedule"

def insert_schedule(data):
    return db.insert(SCHEMA, SCHEDULE_TABLE, [data])

def get_schedules_by_time(time_str):
    return db.sql(f"SELECT * FROM {SCHEMA}.{SCHEDULE_TABLE} WHERE time = '{time_str}'")

def create_alerts_table():
    try:
        existing = db.describe_all()
        if TABLE_ALERTS not in [table["name"] for table in existing.get(SCHEMA, {}).get("tables", [])]:
            db.create_table(SCHEMA, TABLE_ALERTS, "id")
    except Exception as e:
        print("Error checking or creating alerts table:", e)


create_alerts_table()

def insert_alert(email, workout_id, alert_time):
    alert_id = f"{email}_{workout_id}_{alert_time}"
    alert_data = {
        "id": alert_id,
        "email": email,
        "workout_id": workout_id,
        "alert_time": alert_time
    }
    return db.insert(SCHEMA, TABLE_ALERTS, [alert_data])

def get_alerts_by_time(current_time):
    return db.sql(f"SELECT * FROM {SCHEMA}.{TABLE_ALERTS} WHERE alert_time = '{current_time}'")


