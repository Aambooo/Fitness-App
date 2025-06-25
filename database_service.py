from typing import List, Dict, Any, Optional
import mysql.connector
from mysql.connector import Error, pooling
import os
import bcrypt
import time
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database_service.log'),
        logging.StreamHandler()
    ]
)

load_dotenv()

class DatabaseService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.connection_pool = None
            self.create_connection_pool()
            self._initialized = True
            logging.info("DatabaseService initialized")

    def create_connection_pool(self):
        """Create a connection pool for better performance"""
        try:
            self.connection_pool = pooling.MySQLConnectionPool(
                pool_name="fitness_pool",
                pool_size=5,
                host='localhost',
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', ''),
                database='fitness_app',
                autocommit=True
            )
            logging.info("MySQL Connection pool created successfully")
        except Error as e:
            logging.error(f"Error creating connection pool: {e}")
            raise
    
    def get_connection(self):
        """Get a connection from the pool"""
        try:
            return self.connection_pool.get_connection()
        except Error as e:
            logging.error(f"Error getting connection from pool: {e}")
            raise
    
    def __del__(self):
        """Proper connection pool cleanup"""
        try:
            if hasattr(self, 'connection_pool') and self.connection_pool:
            # Correct way to close MySQL connection pool
               self.connection_pool._remove_connections()
               logging.info("Connection pool closed successfully")
        except Exception as e:
            logging.error(f"Cleanup error: {e}")

    # User Authentication Methods
    def verify_user_password(self, email: str, password: str) -> bool:
        """
        Verify user credentials against database
        Args:
            email: User's email address
            password: Password to verify
        Returns:
            bool: True if credentials are valid, False otherwise
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Get user's password hash
            cursor.execute(
                "SELECT password_hash FROM users WHERE email = %s", 
                (email,)
            )
            user = cursor.fetchone()
            
            if not user or not user.get('password_hash'):
                return False
                
            # Verify password against stored hash
            return bcrypt.checkpw(
                password.encode('utf-8'), 
                user['password_hash'].encode('utf-8')
            )
        except Error as e:
            logging.error(f"Error verifying password for {email}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email or google_id"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM users WHERE email = %s OR google_id = %s"
            cursor.execute(query, (email, email))
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Error fetching user {email}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def register_user(self, email: str, password: Optional[str] = None, 
                    full_name: Optional[str] = None, google_id: Optional[str] = None) -> tuple[bool, str]:
        """Register a new user with validation"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.get_user_by_email(email):
                return False, "Email already registered"
            
            user_id = f"usr_{int(time.time() * 1000)}"
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() if password else None
            
            query = """
                INSERT INTO users 
                (user_id, email, password_hash, full_name, google_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                user_id, email, hashed_pw, 
                full_name or email.split('@')[0], 
                google_id,
                int(time.time() * 1000),
                int(time.time() * 1000)
            )
            
            cursor.execute(query, values)
            return True, "Registration successful"
        except Error as e:
            logging.error(f"Registration error for {email}: {e}")
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from the database"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT user_id, email, full_name, google_id, created_at, updated_at
                FROM users
                ORDER BY created_at DESC
            """)
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error fetching users: {e}")
            return []
        finally:
            if conn:
                conn.close()

    # Workout Management Methods
    def add_workout(self, workout_data: Dict[str, Any]) -> tuple[bool, str]:
        """Add new workout to database"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
                INSERT INTO all_workouts 
                (video_id, title, channel, duration, added_at)
                VALUES (%s, %s, %s, %s, %s)
            """
            values = (
                workout_data['video_id'],
                workout_data['title'],
                workout_data['channel'],
                workout_data['duration'],
                int(time.time() * 1000)
            )
            
            cursor.execute(query, values)
            return True, "Workout added successfully"
        except Error as e:
            logging.error(f"Error adding workout: {e}")
            return False, str(e)
        finally:
            if conn:
                conn.close()
    
    def get_all_workouts(self) -> List[Dict[str, Any]]:
        """Get all workouts from database"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM all_workouts ORDER BY added_at DESC")
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error fetching workouts: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def set_todays_workout(self, video_id: str) -> tuple[bool, str]:
        """Set today's workout"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if not self.get_workout_by_id(video_id):
                return False, "Workout not found"
            
            cursor.execute("DELETE FROM todays_workout")
            
            query = "INSERT INTO todays_workout (video_id, selected_at) VALUES (%s, %s)"
            cursor.execute(query, (video_id, int(time.time() * 1000)))
            
            cursor.execute("UPDATE all_workouts SET is_todays = FALSE")
            cursor.execute("UPDATE all_workouts SET is_todays = TRUE WHERE video_id = %s", (video_id,))
            
            return True, "Today's workout updated"
        except Error as e:
            logging.error(f"Error setting today's workout: {e}")
            return False, str(e)
        finally:
            if conn:
                conn.close()
    
    def get_todays_workout(self) -> Optional[Dict[str, Any]]:
        """Get today's recommended workout"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            query = """
                SELECT w.* FROM todays_workout t
                JOIN all_workouts w ON t.video_id = w.video_id
                LIMIT 1
            """
            cursor.execute(query)
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Error fetching today's workout: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def get_workout_by_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get specific workout by video_id"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM all_workouts WHERE video_id = %s LIMIT 1"
            cursor.execute(query, (video_id,))
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Error fetching workout: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def delete_workout(self, video_id: str) -> bool:
        """Delete a workout by video_id"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            today = self.get_todays_workout()
            if today and today['video_id'] == video_id:
                cursor.execute("DELETE FROM todays_workout WHERE video_id = %s", (video_id,))
            
            cursor.execute("DELETE FROM all_workouts WHERE video_id = %s", (video_id,))
            return True
        except Error as e:
            logging.error(f"Error deleting workout: {e}")
            return False
        finally:
            if conn:
                conn.close()

    # Schedule Management Methods
    def get_schedule_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user's schedule"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM schedule WHERE email = %s LIMIT 1"
            cursor.execute(query, (email,))
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Error fetching schedule: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def save_schedule(self, email: str, schedule_data: Dict[str, Any]) -> bool:
        """Create or update schedule"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            existing = self.get_schedule_by_email(email)
            data = {
                "email": email,
                **schedule_data,
                "updated_at": int(time.time() * 1000)
            }
            
            if existing:
                query = """
                    UPDATE schedule SET
                    video_id = %s,
                    time = %s,
                    title = %s,
                    channel = %s,
                    duration = %s,
                    user_id = %s,
                    updated_at = %s
                    WHERE email = %s
                """
                values = (
                    data['video_id'],
                    data['time'],
                    data['title'],
                    data['channel'],
                    data['duration'],
                    data['user_id'],
                    data['updated_at'],
                    email
                )
            else:
                query = """
                    INSERT INTO schedule 
                    (email, video_id, time, title, channel, duration, user_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    email,
                    data['video_id'],
                    data['time'],
                    data['title'],
                    data['channel'],
                    data['duration'],
                    data['user_id'],
                    int(time.time() * 1000),
                    data['updated_at']
                )
            
            cursor.execute(query, values)
            return True
        except Error as e:
            logging.error(f"Error saving schedule: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def delete_schedule(self, email: str) -> bool:
        """Delete user's schedule"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedule WHERE email = %s", (email,))
            return True
        except Error as e:
            logging.error(f"Error deleting schedule: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def get_schedules_by_time(self, target_time: str) -> List[Dict[str, Any]]:
        """Get schedules matching target_time (24-hour format only)"""
        conn = None
        try:
        # Validate and normalize to 24-hour format
            try:
                hour, minute = map(int, target_time.split(':'))
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                   raise ValueError
                normalized_time = f"{hour:02d}:{minute:02d}"
            except ValueError:
                logging.error(f"Invalid time format: {target_time}")
                return []
        
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
        
        # Query using exact 24-hour format match
            cursor.execute("SELECT * FROM schedule WHERE time = %s", (normalized_time,))
        
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Database error: {e}")
            return []
        finally:
            if conn:
               conn.close()

    # Add this method to your DatabaseService class
    def get_all_schedules(self) -> List[Dict[str, Any]]:
        """Get all schedules from the database"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM schedule")
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error getting all schedules: {e}")
            return []
        finally:
           if conn:
            conn.close()


if __name__ == "__main__":
    dbs = DatabaseService()
    print("✓ DatabaseService verified")
    print("Available methods:", [m for m in dir(dbs) if not m.startswith('_')])
else:
    dbs = DatabaseService()
