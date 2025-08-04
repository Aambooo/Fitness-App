from google.oauth2 import id_token
from google.auth.transport import requests
import dns.resolver  # Add this line
from email_validator import validate_email, EmailNotValidError
import mysql.connector
from email_validator import validate_email, EmailNotValidError 
from typing import List, Dict, Any, Optional, Tuple
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
    

    def get_cursor(self, conn):
        """Get a cursor that automatically clears previous results"""
        cursor = conn.cursor(dictionary=True)
        cursor._connection = conn  # Keep reference to connection
        return cursor

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
            logging.info('DatabaseService initialized')

    def create_connection_pool(self):
        """Create MySQL connection pool with retry logic"""
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                self.connection_pool = pooling.MySQLConnectionPool(
                    pool_name='fitness_pool',
                    pool_size=5,
                    host=os.getenv('DB_HOST', 'localhost'),
                    user=os.getenv('DB_USER', 'root'),
                    password=os.getenv('DB_PASSWORD', ''),
                    database=os.getenv('DB_NAME', 'fitness_app'),
                    autocommit=True,
                    connect_timeout=5
                )
                logging.info('MySQL connection pool created successfully')
                return
            except Error as e:
                logging.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)

    def get_connection(self):
        """Get connection from pool with error handling"""
        try:
            conn = self.connection_pool.get_connection()
            if not conn.is_connected():
                conn.reconnect(attempts=3, delay=1)
            return conn
        except Error as e:
            logging.error(f"Error getting connection: {e}")
            raise

    def __del__(self):
        """Cleanup connection pool"""
        try:
            if hasattr(self, 'connection_pool') and self.connection_pool:
                self.connection_pool._remove_connections()
                logging.info('Connection pool closed')
        except Exception as e:
            logging.error(f"Cleanup error: {e}")

    # User Management
    def verify_user_password(self, email: str, password: str) -> bool:
        """Verify user password against stored hash"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                'SELECT password_hash FROM users WHERE email = %s', 
                (email,)
            )
            user = cursor.fetchone()
            
            if not user or not user.get('password_hash'):
                return False
                
            return bcrypt.checkpw(
                password.encode('utf-8'),
                user['password_hash'].encode('utf-8')
            )
        except Error as e:
            logging.error(f"Password verification failed for {email}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email or Google ID"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            query = '''
                SELECT * FROM users 
                WHERE email = %s OR google_id = %s
            '''
            cursor.execute(query, (email, email))
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Error fetching user {email}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def verify_email_domain(self, email: str) -> bool:
        """Check if email domain has valid MX records"""
        try:
            domain = email.split('@')[1]
            records = dns.resolver.resolve(domain, 'MX')
            return bool(records)
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            return False
        except Exception as e:
            logging.error(f"DNS verification failed for {email}: {e}")
            return False  # Fail-safe: assume valid if DNS check fails

    def register_user(self, email: str, 
                    password: Optional[str] = None,
                    full_name: Optional[str] = None,
                    google_id: Optional[str] = None) -> Tuple[bool, str]:
        """Register new user with email or Google auth"""
        conn = None
        try:

            if google_id is None:  # Only validate if not Google sign-in
                valid = validate_email(email)
                email = valid.email 
            
            if not self.verify_email_domain(email):
                return False, "Email domain does not exist"

            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if user exists
            if self.get_user_by_email(email):
                return False, 'Email already registered'
                
            # Generate user data
            user_id = f"usr_{int(time.time()*1000)}"
            hashed_pw = (bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() 
                        if password else None)
            
            query = '''
                INSERT INTO users 
                (user_id, email, password_hash, full_name, google_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            '''
            values = (
                user_id,
                email,
                hashed_pw,
                full_name or email.split('@')[0],
                google_id,
                int(time.time()*1000),
                int(time.time()*1000)
            )
            
            cursor.execute(query, values)
            return True, 'Registration successful'
        
        except EmailNotValidError as e:  # NEW EXCEPTION HANDLING
            return False, f'Invalid email: {str(e)}'
    
        except Error as e:
            logging.error(f"Registration failed for {email}: {e}")
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def register_with_google(self, token: str) -> Tuple[bool, str]:
        """Register/login user using Google OAuth token"""
        try:
            # Verify Google ID token
            id_info = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                os.getenv('GOOGLE_CLIENT_ID')  # Ensure this is in your .env
        )
        
            # Check if email exists
            if self.get_user_by_email(id_info['email']):
                return False, "Email already registered"
            
            # Create new user
            user_id = f"usr_{int(time.time()*1000)}"
            query = """
                INSERT INTO users 
                (user_id, email, full_name, google_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            values = (
                user_id,
                id_info['email'],
                id_info.get('name', id_info['email'].split('@')[0]),  # Fallback to email prefix if no name
                id_info['sub'],  # Google's unique user ID
                int(time.time()*1000),
                int(time.time()*1000)
            )
        
            conn = self.get_connection()
            conn.cursor().execute(query, values)
            conn.commit()
            return True, "Google registration successful"
        
        except ValueError as e:
            logging.error(f"Google auth failed: {e}")
            return False, f"Invalid Google token: {e}"
        except Error as e:
            logging.error(f"Database error during Google registration: {e}")
            return False, "Registration error"

    def get_todays_workout(self) -> Optional[Dict[str, Any]]:
        """Get today's selected workout from database"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
        
        # Query that joins the todays_workout table with all_workouts
            query = '''
                SELECT w.* FROM todays_workout t
                JOIN all_workouts w ON t.video_id = w.video_id
                ORDER BY t.selected_at DESC
                LIMIT 1
            '''
            cursor.execute(query)
            return cursor.fetchone()
        
        except Error as e:
            logging.error(f"Error fetching today's workout: {e}")
            return None
        finally:
            if conn:
                conn.close()

    # Workout Management
    def add_workout(self, workout_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Add new workout to database"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = '''
                INSERT INTO all_workouts 
                (video_id, title, channel, duration, added_at)
                VALUES (%s, %s, %s, %s, %s)
            '''
            values = (
                workout_data['video_id'],
                workout_data['title'],
                workout_data['channel'],
                workout_data['duration'],
                int(time.time()*1000)
            )
            
            cursor.execute(query, values)
            return True, 'Workout added successfully'
            
        except Error as e:
            logging.error(f"Error adding workout: {e}")
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def get_all_workouts(self) -> List[Dict[str, Any]]:
        """Get all workouts sorted by date"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT * FROM all_workouts 
                ORDER BY added_at DESC
            ''')
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error fetching workouts: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def get_all_workouts_with_urls(self) -> List[Dict[str, Any]]:
        """Fetch all workouts with properly formatted video URLs"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT 
                    *,
                    CONCAT('https://youtu.be/', video_id) AS video_url
                FROM all_workouts 
                ORDER BY added_at DESC
            ''')
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error fetching workouts: {e}")
            return []
        finally:
            if conn: conn.close()
    
    def get_workout_by_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific workout by its video ID with complete details"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
        
            query = """
                SELECT 
                    w.*,
                    IFNULL(t.video_id, NULL) AS is_todays_workout
                FROM all_workouts w
                LEFT JOIN todays_workout t ON w.video_id = t.video_id
                WHERE w.video_id = %s
                LIMIT 1
            """
            cursor.execute(query, (video_id,))
            workout = cursor.fetchone()
         
            if workout:
            # Convert duration to formatted string
                workout['duration_text'] = self._format_duration(workout['duration'])
            # Convert boolean flag
                workout['is_todays_workout'] = bool(workout['is_todays_workout'])
        
            return workout
        
        except Error as e:
            logging.error(f"Error fetching workout {video_id}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def delete_workout(self, video_id: str) -> bool:
        """Delete a workout from all_workouts table"""
        conn = None
        try:
            # Validate input
            if not video_id:
                raise ValueError("Empty video_id provided")

            conn = self.get_connection()
            cursor = conn.cursor()
        
            # First check if workout exists
            cursor.execute("SELECT 1 FROM all_workouts WHERE video_id = %s", (video_id,))
            if not cursor.fetchone():
                logging.warning(f"Workout {video_id} not found")
                return False
            
        # Perform deletion
            cursor.execute("DELETE FROM all_workouts WHERE video_id = %s", (video_id,))
            conn.commit()
        
        # Verify deletion
            cursor.execute("SELECT 1 FROM all_workouts WHERE video_id = %s", (video_id,))
            if cursor.fetchone():
                raise Exception("Deletion verification failed")
            
            logging.info(f"Deleted workout {video_id}")
            return True
        
        except Exception as e:
            logging.error(f"Delete failed for {video_id}: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: conn.close()

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Helper to format duration seconds to HH:MM:SS"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"

    def set_todays_workout(self, video_id: str) -> Tuple[bool, str]:
        """Set today's featured workout"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if not self.get_workout_by_id(video_id):
                return False, 'Workout not found'
                
            # Transaction block
            cursor.execute('START TRANSACTION')
            
            try:
                cursor.execute('DELETE FROM todays_workout')
                cursor.execute('''
                    INSERT INTO todays_workout (video_id, selected_at) 
                    VALUES (%s, %s)
                ''', (video_id, int(time.time()*1000)))
                
                cursor.execute('UPDATE all_workouts SET is_todays = FALSE')
                cursor.execute('''
                    UPDATE all_workouts 
                    SET is_todays = TRUE 
                    WHERE video_id = %s
                ''', (video_id,))
                
                conn.commit()
                return True, "Today's workout updated"
                
            except Error as e:
                conn.rollback()
                raise
                
        except Error as e:
            logging.error(f"Error setting workout: {e}")
            return False, str(e)
        finally:
            if conn:
                conn.close()
    
    

    # Schedule Management
    def get_schedule_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get schedule for a specific email with all timestamp fields"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT *, "
                "FROM_UNIXTIME(created_at/1000) as created_at_formatted, "
                "FROM_UNIXTIME(updated_at/1000) as updated_at_formatted "
                "FROM schedule WHERE email = %s",
                (email,)
            )
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Error fetching schedule for {email}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_schedules_by_time(self, time_str: str) -> List[Dict[str, Any]]:
        """Get schedules matching a specific time (HH:MM format)."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = self.get_cursor(conn)
            cursor.execute('''
                SELECT * FROM schedule
                WHERE time = %s AND is_sent = FALSE
                ORDER BY time ASC               
            ''',(time_str,))
            return cursor.fetchall() 
        except Error as e:
            logging.error(f"Error fetching schedules for time {time_str}: {e}")
            return []
        finally:
            if conn: conn.close()

    def save_schedule(self, email: str, schedule_data: Dict[str, Any]) -> bool:
        """Create or update a schedule with proper timestamp handling"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            current_time = int(time.time() * 1000) 
            existing = self.get_schedule_by_email(email)
            
            
            if existing:
                query = '''
                    UPDATE schedule SET
                    video_id = %s,
                    time = %s,
                    title = %s,
                    channel = %s,
                    duration = %s,
                    user_id = %s,
                    updated_at = %s
                    WHERE email = %s
                '''
                values = (
                    schedule_data['video_id'],
                    schedule_data['time'],
                    schedule_data['title'],
                    schedule_data['channel'],
                    schedule_data['duration'],
                    schedule_data['user_id'],
                    current_time,
                    email
                )
            else:
                query = '''
                    INSERT INTO schedule 
                    (email, video_id, time, title, channel, duration, user_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                '''
                values = (
                    email,
                    schedule_data['video_id'],
                    schedule_data['time'],
                    schedule_data['title'],
                    schedule_data['channel'],
                    schedule_data['duration'],
                    schedule_data['user_id'],
                    current_time,
                    current_time
                )
            
            cursor.execute(query, values)
            conn.commit()
            return True
            
        except Error as e:
            logging.error(f"Error saving schedule: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def get_due_reminders(self, current_time: int) -> List[Dict[str, Any]]:
        """Fetch reminders where time <= current_time AND is_sent = False."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            query = """
                SELECT * FROM schedule 
                WHERE time <= %s AND is_sent = FALSE
                ORDER BY time ASC
            """
            cursor.execute(query, (current_time,))
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error fetching due reminders: {e}")
            return []
        finally:
            if conn: conn.close()

    def mark_reminder_as_sent(self, email: str) -> bool:
        """Set is_sent = TRUE after sending the email."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            query = "UPDATE schedule SET is_sent = TRUE WHERE email = %s"
            cursor.execute(query, (email,))
            conn.commit()
            return True
        except Error as e:
            logging.error(f"Error marking reminder as sent: {e}")
            return False
        finally:
            if conn: conn.close()

# Singleton instance
if __name__ == '__main__':
    dbs = DatabaseService()
    print('✓ DatabaseService verified')
    print('Available methods:', [m for m in dir(dbs) if not m.startswith('_')])
else:
    dbs = DatabaseService()