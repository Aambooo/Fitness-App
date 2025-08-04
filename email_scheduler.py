import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from database_service import dbs
import os
from dotenv import load_dotenv
import logging
import sys
import ssl
from typing import Dict, Any, Optional

# UTF-8 encoding setup
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("email_scheduler.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class EmailScheduler:
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 5
        self.smtp_timeout = 30
        self.smtp_config = {
            "server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            "port": int(os.getenv("SMTP_PORT", 587)),
            "user": os.getenv("SMTP_USER"),
            "password": os.getenv("SMTP_PASS"),
        }
        self.validate_config()

    def validate_config(self):
        """Validate required SMTP configuration"""
        if not all(self.smtp_config.values()):
            logger.error("Missing SMTP configuration in environment variables")
            raise ValueError("Incomplete SMTP configuration")

    def get_current_time(self) -> str:
        """Get current time in HH:MM format"""
        return datetime.now().strftime("%H:%M")

    def create_smtp_connection(self) -> Optional[smtplib.SMTP]:
        """Establish SMTP connection with retry logic"""
        for attempt in range(1, self.max_retries + 1):
            try:
                context = ssl.create_default_context()
                server = smtplib.SMTP(
                    self.smtp_config["server"],
                    self.smtp_config["port"],
                    timeout=self.smtp_timeout,
                )
                server.starttls(context=context)
                server.login(self.smtp_config["user"], self.smtp_config["password"])
                logger.info("SMTP connection established")
                return server
            except Exception as e:
                logger.warning(f"SMTP connection attempt {attempt} failed: {str(e)}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
        return None

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send email with proper error handling"""
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = f"Fitness Reminder <{self.smtp_config['user']}>"
        msg["To"] = to_email

        try:
            with self.create_smtp_connection() as server:
                if server:
                    server.send_message(msg)
                    logger.info(f"Email sent to {to_email}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def process_reminder(self, reminder: Dict[str, Any]) -> bool:
        """Process and send a single reminder"""
        try:
            workout = dbs.get_workout_by_id(reminder["video_id"])
            if not workout:
                logger.error(f"Workout not found: {reminder['video_id']}")
                return False

            email_body = f"""Hello!

Your scheduled workout is ready:

{workout['title']}
Duration: {workout['duration']} seconds
Watch now: https://youtu.be/{workout['video_id']}

Stay active!
Your Fitness App Team
"""

            if self.send_email(reminder["email"], "Your Workout Reminder", email_body):
                return self.mark_reminder_sent(reminder)
            return False
        except Exception as e:
            logger.error(f"Error processing reminder: {str(e)}")
            return False

    def mark_reminder_sent(self, reminder: Dict[str, Any]) -> bool:
        """Mark reminder as sent in database"""
        try:
            conn = dbs.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE schedule 
                    SET is_sent = TRUE 
                    WHERE email = %s AND video_id = %s
                """,
                    (reminder["email"], reminder["video_id"]),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to mark reminder as sent: {str(e)}")
            return False
        finally:
            if conn:
                conn.close()

    def check_and_send_reminders(self):
        """Main scheduler loop to check and send reminders"""
        logger.info("Starting reminder scheduler")

        while True:
            current_time = self.get_current_time()
            logger.debug(f"Checking reminders at {current_time}")

            try:
                reminders = self.get_due_reminders(current_time)
                if reminders:
                    logger.info(f"Processing {len(reminders)} reminders")
                    success_count = sum(self.process_reminder(r) for r in reminders)
                    logger.info(
                        f"Successfully processed {success_count}/{len(reminders)} reminders"
                    )

                # Sleep until next minute
                time.sleep(60 - datetime.now().second)

            except Exception as e:
                logger.error(f"Scheduler error: {str(e)}")
                time.sleep(60)  # Wait before retrying

    def get_due_reminders(self, current_time: str) -> list:
        """Fetch due reminders from database"""
        conn = None
        try:
            conn = dbs.get_connection()
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM schedule 
                    WHERE time = %s AND is_sent = FALSE
                """,
                    (current_time,),
                )
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error fetching reminders: {str(e)}")
            return []
        finally:
            if conn:
                conn.close()


def manual_test():
    """Test email sending functionality"""
    test_email = input("Enter test email address: ")
    scheduler = EmailScheduler()

    test_body = """This is a test email from Fitness Reminder App.

If you're receiving this, the email scheduler is working correctly!"""

    success = scheduler.send_email(test_email, "Fitness App Test Email", test_body)

    print(f"\nTest {'succeeded' if success else 'failed'}")


if __name__ == "__main__":
    print("Fitness Reminder Email Scheduler")
    print("1. Run scheduler")
    print("2. Test email sending")
    choice = input("Select option (1/2): ")

    if choice == "2":
        manual_test()
    else:
        scheduler = EmailScheduler()
        try:
            scheduler.check_and_send_reminders()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        except Exception as e:
            logger.error(f"Scheduler crashed: {str(e)}")
