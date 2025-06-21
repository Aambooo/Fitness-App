import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import database_service as dbs
import os
from dotenv import load_dotenv
import logging
from typing import List, Dict, Any

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_scheduler.log'),
        logging.StreamHandler()
    ]
)

# Email configuration from environment
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Validate configuration
if not all([EMAIL_ADDRESS, EMAIL_PASSWORD]):
    logging.error("Missing email configuration in environment variables")
    exit(1)

def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email with proper error handling"""
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email
        
        # This is where your SMTP code lives now (secure version)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        
        logging.info(f"Email sent successfully to {to_email}")
        return True
    except smtplib.SMTPException as e:
        logging.error(f"SMTP error sending to {to_email}: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error sending to {to_email}: {str(e)}")
    return False

def check_alerts() -> None:
    """Check for scheduled alerts and send emails"""
    current_time = datetime.now().strftime("%H:%M")
    logging.info(f"Checking alerts at {current_time}")
    
    try:
        schedules = dbs.get_schedules_by_time(current_time)
        if not schedules:
            logging.info("No scheduled reminders found for this time")
            return
            
        logging.info(f"Found {len(schedules)} scheduled reminders")
        
        for schedule in schedules:
            if not all(key in schedule for key in ['email', 'title', 'video_id']):
                logging.warning("Invalid schedule data, skipping")
                continue
                
            email = schedule['email']
            title = schedule['title']
            video_id = schedule['video_id']
            
            logging.info(f"Processing reminder for {email} (Workout: {title})")
            
            email_sent = send_email(
                email,
                "⏰ Workout Reminder!",
                f"Time for your workout: {title}\nWatch: https://youtu.be/{video_id}"
            )
            
            if email_sent:
                # Optional: Update database to mark as sent
                pass
                
    except Exception as e:
        logging.error(f"Error processing alerts: {str(e)}")

def main() -> None:
    """Main scheduler loop"""
    logging.info("🚀 Email scheduler started")
    
    # Calculate sleep time to align with whole minutes
    next_minute = (datetime.now() + timedelta(minutes=1)).replace(second=0, microsecond=0)
    initial_delay = (next_minute - datetime.now()).total_seconds()
    time.sleep(initial_delay)
    
    while True:
        try:
            check_alerts()
            # Sleep until next whole minute
            time.sleep(60 - time.time() % 60)
        except KeyboardInterrupt:
            logging.info("🛑 Scheduler stopped by user")
            break
        except Exception as e:
            logging.error(f"Unexpected error in main loop: {str(e)}")
            time.sleep(60)  # Prevent tight loop on errors

if __name__ == "__main__":
    main()