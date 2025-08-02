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

    def register_user(self, email: str, 
                    password: Optional[str] = None,
                    full_name: Optional[str] = None,
                    google_id: Optional[str] = None) -> Tuple[bool, str]:
        """Register new user with email or Google auth"""
        conn = None
        try:
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
            
        except Error as e:
            logging.error(f"Registration failed for {email}: {e}")
            return False, str(e)
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
    def save_schedule(self, email: str, schedule_data: Dict[str, Any]) -> bool:
        """Save or update email schedule"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            existing = self.get_schedule_by_email(email)
            
            data = {
                'email': email,
                **schedule_data,
                'updated_at': int(time.time()*1000)
            }
            
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
                query = '''
                    INSERT INTO schedule 
                    (email, video_id, time, title, channel, duration, user_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                '''
                values = (
                    email,
                    data['video_id'],
                    data['time'],
                    data['title'],
                    data['channel'],
                    data['duration'],
                    data['user_id'],
                    int(time.time()*1000),
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

# Singleton instance
if __name__ == '__main__':
    dbs = DatabaseService()
    print('✓ DatabaseService verified')
    print('Available methods:', [m for m in dir(dbs) if not m.startswith('_')])
else:
    dbs = DatabaseService()