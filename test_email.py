import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import ssl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def send_test_email() -> bool:
    """Send a test email using configured SMTP settings"""
    load_dotenv()  # Load environment variables

    # Get configuration from environment
    smtp_config = {
        "server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", 587)),
        "user": os.getenv("SMTP_USER"),
        "password": os.getenv("SMTP_PASS"),
        "to_email": os.getenv("TEST_RECIPIENT", "recipient@example.com"),
    }

    # Validate configuration
    if not all(smtp_config.values()):
        logger.error("Missing SMTP configuration in .env file")
        return False

    try:
        # Create secure email message
        msg = MIMEText(
            f"This is a test email sent at {datetime.now()}\n\n"
            "If you received this, your email configuration is working correctly!",
            "plain",
            "utf-8",
        )
        msg["Subject"] = "Fitness App Test Email"
        msg["From"] = f"Fitness App <{smtp_config['user']}>"
        msg["To"] = smtp_config["to_email"]

        # Create secure SMTP connection
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_config["server"], smtp_config["port"]) as server:
            server.starttls(context=context)
            server.login(smtp_config["user"], smtp_config["password"])
            server.send_message(msg)

        logger.info(f"Test email successfully sent to {smtp_config['to_email']}")
        return True

    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    return False


if __name__ == "__main__":
    print(f"\n=== Email Configuration Test at {datetime.now()} ===")
    if send_test_email():
        print("✅ Test succeeded - check recipient's inbox")
    else:
        print("❌ Test failed - check logs for details")
    print("\nNote: Ensure your .env file contains:")
    print("SMTP_SERVER=smtp.yourprovider.com")
    print("SMTP_PORT=587")
    print("SMTP_USER=your@email.com")
    print("SMTP_PASS=your_password")
    print("TEST_RECIPIENT=recipient@example.com")
