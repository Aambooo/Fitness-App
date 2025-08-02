import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from database_service import dbs
import os
from dotenv import load_dotenv
import logging
from typing import List, Dict, Any, Optional
import sys
import ssl  # Added for better SSL handling

# Windows console encoding fix
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Load environment variables
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
    'timeout': 30  # Increased timeout for slow connections
}

# Validate configuration
if not all(SMTP_CONFIG.values()):
    logger.error("Missing email configuration in environment variables")
    exit(1)

class EmailScheduler:
    def __init__(self):
        self.last_run = None
        self.retry_count = 0
        self.max_retries = 3

    @staticmethod
    def get_current_time_formatted() -> str:
        """Get current time in HH:MM format"""
        now = datetime.now()
        return f"{now.hour:02d}:{now.minute:02d}"

    def create_smtp_connection(self) -> Optional[smtplib.SMTP]:
        """Create secure SMTP connection with retry logic"""
        try:
            context = ssl.create_default_context()
            server = smtplib.SMTP(
                SMTP_CONFIG['server'], 
                SMTP_CONFIG['port'],
                timeout=SMTP_CONFIG['timeout']
            )
            
            server.set_debuglevel(1)  # Debug output
            server.starttls(context=context)
            server.login(SMTP_CONFIG['address'], SMTP_CONFIG['password'])
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
        """Send email with enhanced error handling"""
        try:
            msg = MIMEText(body, 'plain', 'utf-8')
            msg["Subject"] = subject
            msg["From"] = f"FitTrackPro <{SMTP_CONFIG['address']}>"
            msg["To"] = to_email

            with self.create_smtp_connection() as server:
                if server:
                    server.send_message(msg)
                    logger.info(f"Email sent to {to_email}")
                    self.retry_count = 0  # Reset on success
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False

    def process_schedule(self, schedule: Dict[str, Any]) -> bool:
        """Process individual schedule entry"""
        required_keys = {'email', 'title', 'video_id'}
        if not required_keys.issubset(schedule.keys()):
            missing = required_keys - set(schedule.keys())
            logger.warning(f"Invalid schedule - missing {missing}")
            return False

        email = schedule['email']
        title = schedule['title']
        video_url = f"https://youtu.be/{schedule['video_id']}"
        
        logger.info(f"Processing reminder for {email} - {title}")
        return self.send_email(
            email,
            "Your Daily Workout Reminder!",
            f"""Hi there!\n\nIt's time for your scheduled workout:
            \nWorkout: {title}
            \nWatch now: {video_url}
            \n\nStay fit!\nThe FitTrackPro Team"""
        )

    def check_alerts(self) -> None:
        """Check and process all scheduled alerts"""
        current_time = self.get_current_time_formatted()
        logger.info(f"Checking alerts at {current_time}")
        
        try:
            schedules = dbs.get_schedules_by_time(current_time)
            if not schedules:
                logger.debug(f"No reminders for {current_time}")
                return

            logger.info(f"Found {len(schedules)} reminders")
            success_count = sum(self.process_schedule(s) for s in schedules)
            logger.info(f"Processed {success_count}/{len(schedules)} successfully")

        except Exception as e:
            logger.error(f"Error processing alerts: {str(e)}", exc_info=True)

    def run(self) -> None:
        """Main scheduler loop with precise timing"""
        logger.info("Starting FitTrackPro Email Scheduler")
        
        # Align with whole minutes
        next_run = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=1)
        initial_delay = (next_run - datetime.now()).total_seconds()
        time.sleep(max(0, initial_delay))
        
        while True:
            try:
                start_time = time.time()
                self.check_alerts()
                self.last_run = datetime.now()
                
                # Sleep until next whole minute
                sleep_time = 60 - (time.time() % 60)
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user")
                break
            except Exception as e:
                logger.error(f"Main loop error: {str(e)}")
                time.sleep(60)  # Prevent tight error loop

if __name__ == "__main__":
    scheduler = EmailScheduler()
    scheduler.run()