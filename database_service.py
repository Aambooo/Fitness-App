import mysql.connector
from mysql.connector import Error, pooling
import os
import bcrypt
import time
import logging
import dns.resolver
from email_validator import validate_email, EmailNotValidError
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("database_service.log"), logging.StreamHandler()],
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
        if not getattr(self, "_initialized", False):
            self.connection_pool = None
            self._create_connection_pool()
            self._create_tables()
            self._initialized = True
            logging.info("DatabaseService initialized with MySQL")
            print("🔥 DEBUG: DatabaseService fully initialized")

    def _create_connection_pool(self):
        """Create MySQL connection pool with retry logic"""
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                self.connection_pool = pooling.MySQLConnectionPool(
                    pool_name="fitness_pool",
                    pool_size=5,
                    host=os.getenv("DB_HOST", "localhost"),
                    user=os.getenv("DB_USER", "root"),
                    password=os.getenv("DB_PASSWORD", ""),
                    database=os.getenv("DB_NAME", "fitness_app"),
                    autocommit=True,
                    connect_timeout=5,
                )
                logging.info("MySQL connection pool created successfully")
                return
            except Error as e:
                logging.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)

    def _create_tables(self):
        """Create required tables if they don't exist"""
        conn = None
        try:
            conn = self.connection_pool.get_connection()
            cursor = conn.cursor(dictionary=True)

            # Users table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(255) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name VARCHAR(255),
                    is_verified BOOLEAN DEFAULT FALSE,
                    created_at BIGINT
                )
            """
            )

            # Workouts table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS all_workouts (
                    video_id VARCHAR(255) PRIMARY KEY,
                    title TEXT NOT NULL,
                    channel TEXT,
                    duration INT,
                    added_at BIGINT
                )
            """
            )

            # Today's workout table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS todays_workout (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    video_id VARCHAR(255),
                    selected_at BIGINT,
                    FOREIGN KEY (video_id) REFERENCES all_workouts(video_id)
                )
            """
            )

            # Schedule table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schedule (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255),
                    video_id VARCHAR(255),
                    time VARCHAR(50),
                    title TEXT,
                    user_id VARCHAR(255),
                    created_at BIGINT,
                    updated_at BIGINT,
                    FOREIGN KEY (email) REFERENCES users(email),
                    FOREIGN KEY (video_id) REFERENCES all_workouts(video_id)
                )
            """
            )

            conn.commit()
            logging.info("Tables created/verified successfully")
        except Error as e:
            logging.error(f"Error creating tables: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def get_connection(self):
        """Get connection with debug validation"""
        if not self.connection_pool:
            print("🚨 CRITICAL: Connection pool not initialized!")
            self._create_connection_pool()

        try:
            conn = self.connection_pool.get_connection()
            print(f"🔥 Connection established (ID: {conn.connection_id})")
            return conn
        except Error as e:
            print(f"🚨 Connection failed: {str(e)}")
            raise

    def __del__(self):
        """Cleanup connection pool"""
        try:
            if hasattr(self, "connection_pool") and self.connection_pool:
                self.connection_pool._remove_connections()
                logging.info("Connection pool closed")
        except Exception as e:
            logging.error(f"Cleanup error: {e}")

    # User Management
    def verify_user_password(self, email: str, password: str) -> bool:
        """Verify user password against stored hash"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT password_hash FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if not user or not user.get("password_hash"):
                return False

            return bcrypt.checkpw(
                password.encode("utf-8"), user["password_hash"].encode("utf-8")
            )
        except Error as e:
            logging.error(f"Password verification failed for {email}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def update_user_password(self, email: str, new_hash: str) -> bool:
        """Update user password"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE email = %s",
                (new_hash, email),
            )
            conn.commit()
            return cursor.rowcount > 0
        except Error as e:
            logging.error(f"Password update failed for {email}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    # Add this to database_service.py
    def delete_unverified_users(self, older_than_days=3):
        """Cleanup unverified accounts"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cutoff = int(time.time() * 1000) - (older_than_days * 24 * 60 * 60 * 1000)

            cursor.execute(
                """
               DELETE FROM users 
               WHERE is_verified = FALSE 
               AND created_at < %s
           """,
                (cutoff,),
            )

            conn.commit()
            return cursor.rowcount
        except Error as e:
            logging.error(f"Cleanup failed: {e}")
            return 0

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            return cursor.fetchone()
        except Exception as e:
            logging.error(f"Error fetching user {email}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def verify_email_domain(self, email: str) -> bool:
        """Check if email domain has valid MX records"""
        try:
            domain = email.split("@")[1]
            records = dns.resolver.resolve(domain, "MX")
            return bool(records)
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            return False
        except Exception as e:
            logging.error(f"DNS verification failed for {email}: {e}")
            return False

    def register_user(
        self, email: str, password: str, full_name: str
    ) -> Tuple[bool, str]:
        """Register new user with email/password (unverified by default)

        Args:
            email: User's email address (must be valid)
            password: Plain text password (will be hashed)
            full_name: User's full name

        Returns:
            Tuple of (success: bool, message: str)
        """
        conn = None
        try:
            # 1. Validate email format
            try:
                valid = validate_email(email)
                email = valid.email  # Normalized email
            except EmailNotValidError as e:
                return False, f"Invalid email: {str(e)}"

            # 2. Verify email domain exists
            if not self.verify_email_domain(email):
                return False, "Email domain does not exist"

            # 3. Check password strength (minimum 8 chars)
            if len(password) < 8:
                return False, "Password must be at least 8 characters"

            conn = self.get_connection()
            cursor = conn.cursor()

            # 4. Check if email already exists (verified or unverified)
            if self.get_user_by_email(email):
                return False, "Email already registered"

            # 5. Create user record
            user_id = f"usr_{int(time.time()*1000)}"
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            created_at = int(time.time() * 1000)

            cursor.execute(
                """
                INSERT INTO users 
                (user_id, email, password_hash, full_name, is_verified, created_at)
                VALUES (%s, %s, %s, %s, FALSE, %s)
                """,
                (user_id, email, hashed_pw, full_name, created_at),
            )
            conn.commit()

            logging.info(f"New user registered (unverified): {email}")
            return True, "Verification email sent"

        except Error as e:
            logging.error(f"Registration failed for {email}: {str(e)}")
            return False, "Registration failed. Please try again."

        finally:
            if conn:
                conn.close()

    def delete_user(self, email: str) -> bool:
        """Delete a user by email (for rollback purposes)"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE email = %s", (email,))
            conn.commit()
            return cursor.rowcount > 0
        except Error as e:
            logging.error(f"Failed to delete user {email}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def mark_user_as_verified(self, email: str) -> bool:
        """Mark user as verified in database"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE users SET is_verified = TRUE WHERE email = %s", (email,)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Error as e:
            logging.error(f"Error verifying user {email}: {e}")
            return False
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

            query = """
                INSERT INTO all_workouts 
                (video_id, title, channel, duration, added_at)
                VALUES (%s, %s, %s, %s, %s)
            """
            values = (
                workout_data["video_id"],
                workout_data["title"],
                workout_data["channel"],
                workout_data["duration"],
                int(time.time() * 1000),
            )

            cursor.execute(query, values)
            conn.commit()
            return True, "Workout added successfully"

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

            cursor.execute(
                """
                SELECT * FROM all_workouts 
                ORDER BY added_at DESC
            """
            )
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error fetching workouts: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_all_workouts_with_urls(self) -> List[Dict[str, Any]]:
        """Fetch all workouts with properly formatted video URLs"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT 
                    *,
                    CONCAT('https://youtu.be/', video_id) AS video_url
                FROM all_workouts 
                ORDER BY added_at DESC
            """
            )
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Error fetching workouts: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_workout_by_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific workout by its video ID"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT * FROM all_workouts 
                WHERE video_id = %s
                LIMIT 1
            """,
                (video_id,),
            )
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Error fetching workout {video_id}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def delete_workout(self, video_id: str) -> bool:
        """Delete a workout from database"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM all_workouts WHERE video_id = %s", (video_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Error as e:
            logging.error(f"Delete failed for {video_id}: {e}")
            return False
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
                return False, "Workout not found"

            cursor.execute("DELETE FROM todays_workout")
            cursor.execute(
                """
                INSERT INTO todays_workout (video_id, selected_at) 
                VALUES (%s, %s)
            """,
                (video_id, int(time.time() * 1000)),
            )
            conn.commit()

            return True, "Today's workout updated"

        except Error as e:
            logging.error(f"Error setting workout: {e}")
            return False, str(e)
        finally:
            if conn:
                conn.close()

    # Schedule Management
    def get_schedule_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get schedule for a specific email"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT * FROM schedule WHERE email = %s", (email,))
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Error fetching schedule for {email}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def save_schedule(self, email: str, schedule_data: Dict[str, Any]) -> bool:
        """Create or update a schedule"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            current_time = int(time.time() * 1000)
            existing = self.get_schedule_by_email(email)

            if existing:
                query = """
                    UPDATE schedule SET
                    video_id = %s,
                    time = %s,
                    title = %s,
                    user_id = %s,
                    updated_at = %s
                    WHERE email = %s
                """
                values = (
                    schedule_data["video_id"],
                    schedule_data["time"],
                    schedule_data["title"],
                    schedule_data["user_id"],
                    current_time,
                    email,
                )
            else:
                query = """
                    INSERT INTO schedule 
                    (email, video_id, time, title, user_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    email,
                    schedule_data["video_id"],
                    schedule_data["time"],
                    schedule_data["title"],
                    schedule_data["user_id"],
                    current_time,
                    current_time,
                )

            cursor.execute(query, values)
            conn.commit()
            return True

        except Error as e:
            logging.error(f"Error saving schedule: {e}")
            return False
        finally:
            if conn:
                conn.close()


# Singleton instance
dbs = DatabaseService()
