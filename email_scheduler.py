from typing import Optional  # Add this with other imports
from typing import List, Dict, Any, Optional  # All type hints you need
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from database_service import dbs
import os
from dotenv import load_dotenv
import logging
import sys
import ssl

# UTF-8 encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Email configuration
SMTP_CONFIG = {
    'server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
    'port': int(os.getenv('SMTP_PORT', 587)),
    'address': os.getenv('EMAIL_ADDRESS'),
    'password': os.getenv('EMAIL_PASSWORD'),
    'timeout': 30
}

if not all(SMTP_CONFIG.values()):
    logger.error('Missing email configuration in environment variables')
    exit(1)

class EmailScheduler:
    def __init__(self):
        self.last_run = None
        self.retry_count = 0
        self.max_retries = 3
        self.smtp_connection = None

    @staticmethod
    def get_current_time_formatted() -> str:
        """Get current time in HH:MM format"""
        now = datetime.now()
        return f"{now.hour:02d}:{now.minute:02d}"

    def create_smtp_connection(self) -> Optional[smtplib.SMTP]:
        """Create and return SMTP connection with retries"""
        try:
            context = ssl.create_default_context()
            server = smtplib.SMTP(
                SMTP_CONFIG['server'],
                SMTP_CONFIG['port'],
                timeout=SMTP_CONFIG['timeout']
            )
            server.starttls(context=context)
            server.login(SMTP_CONFIG['address'], SMTP_CONFIG['password'])
            logger.info("SMTP connection established")
            return server
        except smtplib.SMTPException as e:
            logger.error(f"SMTP connection failed: {str(e)}")
            if self.retry_count < self.max_retries:
                self.retry_count += 1
                logger.info(f"Retrying connection ({self.retry_count}/{self.max_retries})")
                time.sleep(5)
                return self.create_smtp_connection()
            return None

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send email with proper error handling"""
        try:
            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = f"FitTrackPro <{SMTP_CONFIG['address']}>"
            msg['To'] = to_email

            with self.create_smtp_connection() as server:
                if server:
                    server.send_message(msg)
                    logger.info(f"Email sent to {to_email}")
                    self.retry_count = 0
                    return True
            return False
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False

    def process_reminder(self, reminder: Dict[str, Any]) -> bool:
        """Process a single reminder"""
        required_keys = {'email', 'video_id'}
        if not all(key in reminder for key in required_keys):
            logger.warning(f"Invalid reminder - missing keys: {required_keys - set(reminder.keys())}")
            return False

        try:
            # Get workout details
            workout = dbs.get_workout_by_id(reminder['video_id'])
            if not workout:
                logger.error(f"No workout found for video_id: {reminder['video_id']}")
                return False

            # Prepare email
            subject = "Your Workout Reminder!"
            body = f"""Hi there!

It's time for your scheduled workout:
            
Workout: {workout['title']}
            
Watch now: https://youtu.be/{workout['video_id']}
            

Stay fit!
The FitTrackPro Team"""

            # Send email
            if self.send_email(reminder['email'], subject, body):
                # Mark as sent in database
                conn = dbs.get_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute('''
                            UPDATE schedule 
                            SET is_sent = TRUE 
                            WHERE email = %s AND video_id = %s
                        ''', (reminder['email'], reminder['video_id']))
                        conn.commit()
                    return True
                finally:
                    conn.close()
            return False
        except Exception as e:
            logger.error(f"Error processing reminder: {str(e)}")
            return False

    def check_and_send_reminders(self):
        """Main scheduler loop"""
        logger.info("Starting reminder scheduler")
        
        while True:
            current_time = self.get_current_time_formatted()
            logger.info(f"Checking reminders at {current_time}")
            
            conn = None
            try:
                # Get due reminders
                conn = dbs.get_connection()
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute('''
                        SELECT * FROM schedule 
                        WHERE time = %s AND is_sent = FALSE
                        ORDER BY time ASC
                    ''', (current_time,))
                    reminders = cursor.fetchall()

                logger.info(f"Found {len(reminders)} reminders to process")

                # Process each reminder
                success_count = 0
                for reminder in reminders:
                    if self.process_reminder(reminder):
                        success_count += 1

                logger.info(f"Processed {success_count}/{len(reminders)} reminders successfully")

            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                if conn:
                    conn.rollback()

            finally:
                if conn:
                    conn.close()

            # Wait for next minute
            sleep_time = 60 - (time.time() % 60)
            time.sleep(sleep_time)

def manual_test():
    """Test email sending manually"""
    test_email = os.getenv('TEST_EMAIL', 'your_email@gmail.com')
    test_subject = 'TEST: Workout Reminder'
    test_body = 'This is a manual test email from the scheduler.'
    
    scheduler = EmailScheduler()
    success = scheduler.send_email(test_email, test_subject, test_body)
    
    print(f"\nTEST RESULT: {'SUCCESS' if success else 'FAILED'}")

if __name__ == '__main__':
    logger.info('Starting FitTrackPro Email Scheduler')
    
    # Choose one of these to run:
    
    # 1. Run manual test
    # manual_test()
    
    # 2. Run the scheduler
    scheduler = EmailScheduler()
    scheduler.check_and_send_reminders()