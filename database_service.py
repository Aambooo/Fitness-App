import harperdb
import os
import bcrypt
import time
from datetime import datetime  # Added for timestamp conversion

# Initialize connection
db = harperdb.HarperDB(
    url="http://localhost:9925",
    username="Nabin",
    password="Projectkolagi369$"
)

SCHEMA = "workout_repo"
USERS_TABLE = "users"

def create_users_table():
    """Bulletproof table creation for v4.8.20"""
    try:
        # Method 1: Try using SQL
        try:
            db.sql(f"""
                CREATE TABLE {SCHEMA}.{USERS_TABLE} (
                    user_id VARCHAR(36) PRIMARY KEY,
                    email VARCHAR(250) UNIQUE,
                    password_hash VARCHAR(255),
                    full_name VARCHAR(255),
                    created_at NUMBER,
                    updated_at NUMBER
                )
            """)
            print("✓ Table created via SQL with user_id")
            return True
        except Exception as sql_error:
            # Method 2: Fallback to basic client method
            print("ℹ️ SQL method failed, trying client method...")
            db.create_table(SCHEMA, USERS_TABLE, "user_id")
            
            # Add columns using inserts with the new fields
            test_data = {
                "user_id": "temp_123",
                "email": "temp@example.com",
                "password_hash": "temp",
                "full_name": "Temp User",
                "created_at": int(time.time() * 1000),
                "updated_at": int(time.time() * 1000)
            }
            db.insert(SCHEMA, USERS_TABLE, [test_data])
            db.delete(SCHEMA, USERS_TABLE, ["temp_123"])
            print("✓ Table created via client method with user_id")
            return True
    except Exception as e:
        if "already exists" in str(e).lower():
            print("ℹ️ Table already exists")
            return True
        print(f"❌ Creation failed: {str(e)}")
        return False

def hash_password(password):
    """Hash a password for storing"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(stored_hash, provided_password):
    """Verify a stored password against one provided by user"""
    return bcrypt.checkpw(provided_password.encode(), stored_hash.encode())

def register_user(email, password, full_name, google_id=None):
    """Register a new user with proper password hashing"""
    try:
        # Check if user exists
        if get_user_by_email(email):
            return False, "Email already registered"
        
        # Generate a unique user_id
        user_id = f"usr_{int(time.time() * 1000)}"
        
        # Prepare user data
        timestamp = int(time.time() * 1000)  # Milliseconds since epoch
        user_data = {
            "user_id": user_id,
            "email": email,
            "password_hash": hash_password(password),
            "full_name": full_name,
            "created_at": timestamp,
            "updated_at": timestamp,
            "google_id": google_id
        }
        
        # Insert user
        result = db.insert(SCHEMA, USERS_TABLE, [user_data])
        return True, result
    except Exception as e:
        return False, str(e)

def get_user_by_email(email):
    """Retrieve user by email"""
    try:
        result = db.sql(f"SELECT * FROM {SCHEMA}.{USERS_TABLE} WHERE email = '{email}' LIMIT 1")
        if result:
            return result[0]
        return None
    except Exception as e:
        print(f"Error fetching user: {str(e)}")
        return None

def get_user_by_id(user_id):
    """Retrieve user by user_id"""
    try:
        result = db.sql(f"SELECT * FROM {SCHEMA}.{USERS_TABLE} WHERE user_id = '{user_id}' LIMIT 1")
        if result:
            return result[0]
        return None
    except Exception as e:
        print(f"Error fetching user: {str(e)}")
        return None

def check_table_structure():
    """Verify the users table has all required columns"""
    try:
        # Get one record (or attempt to)
        result = db.sql(f"SELECT * FROM {SCHEMA}.{USERS_TABLE} LIMIT 1")
        
        if not result:
            # If empty, try inserting a test record
            test_data = {
                "email": "structure_check@test.com",
                "password_hash": "test",
                "full_name": "Test User",
                "created_at": int(time.time() * 1000),
                "updated_at": int(time.time() * 1000)
            }
            db.insert(SCHEMA, USERS_TABLE, [test_data])
            result = db.sql(f"SELECT * FROM {SCHEMA}.{USERS_TABLE} LIMIT 1")
            db.delete(SCHEMA, USERS_TABLE, ["structure_check@test.com"])
        
        if result:
            print("✅ Current table structure:")
            for key in result[0].keys():
                print(f" - {key}")
            return True
        else:
            print("❌ Could not determine table structure")
            return False
            
    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        return False

def initialize_database():
    """Safe initialization"""
    print("⚙️ Initializing database...")
    if create_users_table():
        migrate_existing_users()  # Add this line
        print("✅ Database ready")
    else:
        print("❌ Initialization failed")

if __name__ == "__main__":
    initialize_database()
    check_table_structure()
   
def migrate_existing_users():
    """Add user_id to existing users"""
    try:
        # Get all users without user_id
        users = db.sql(f"SELECT * FROM {SCHEMA}.{USERS_TABLE} WHERE user_id IS NULL OR user_id = ''")
        
        for user in users:
            user_id = f"usr_{int(time.time() * 1000)}"
            db.update(SCHEMA, USERS_TABLE, [
                {
                    "email": user['email'],
                    "user_id": user_id
                }
            ])
            time.sleep(0.01)  # Ensure unique timestamps
            
        print(f"✓ Migrated {len(users)} users")
        return True
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        return False

def get_all_workouts():
    """Get all workouts from workout_today table"""
    try:
        workouts = db.sql(f"SELECT * FROM `{SCHEMA}`.`workout_today`")
        return workouts if workouts else []
    except Exception as e:
        print(f"Error fetching workouts: {str(e)}")
        return []
    
def get_workout_today():
    """Get today's workouts from workout_today table"""
    try:
        workouts = db.sql(f"SELECT * FROM `{SCHEMA}`.`workout_today`")
        return workouts if workouts else []
    except Exception as e:
        print(f"Error fetching today's workouts: {str(e)}")
        return []
def get_workout_by_id(workout_id):
    """Get specific workout by ID with error handling"""
    try:
        result = db.sql(f"""
            SELECT * FROM `{SCHEMA}`.`workout_today` 
            WHERE video_id = '{workout_id}' 
            LIMIT 1
        """)
        return result[0] if result else None
    except Exception as e:
        print(f"Error fetching workout {workout_id}: {str(e)}")
        return None

def get_workout_alerts(email):
    """Get workout alerts for a specific user"""
    try:
        alerts = db.sql(f"SELECT * FROM `{SCHEMA}`.`workout_alerts` WHERE email = '{email}'")
        return alerts if alerts else []
    except Exception as e:
        print(f"Error fetching alerts: {str(e)}")
        return []
def get_schedule_by_email(email):
    """Get user's schedule by email"""
    try:
        schedule = db.sql(f"""
            SELECT * FROM `{SCHEMA}`.`schedule` 
            WHERE email = '{email}'
        """)
        return schedule[0] if schedule else None
    except Exception as e:
        print(f"Error fetching schedule: {str(e)}")
        return None

def save_schedule(email, schedule_data):
    """Create or update user schedule"""
    try:
        existing = get_schedule_by_email(email)
        
        if existing:
            # Update existing schedule
            db.update(SCHEMA, "schedule", [{
                "email": email,
                **schedule_data,
                "updated_at": int(time.time() * 1000)
            }])
        else:
            # Create new schedule
            db.insert(SCHEMA, "schedule", [{
                "email": email,
                **schedule_data,
                "created_at": int(time.time() * 1000),
                "updated_at": int(time.time() * 1000)
            }])
        return True
    except Exception as e:
        print(f"Error saving schedule: {str(e)}")
        return False
def delete_schedule(email):
    """Remove user's schedule"""
    try:
        db.delete(SCHEMA, "schedule", [email])
        return True
    except Exception as e:
        print(f"Error deleting schedule: {str(e)}")
        return False