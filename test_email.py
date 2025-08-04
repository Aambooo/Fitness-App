import smtplib
from email.mime.text import MIMEText
from datetime import datetime

def test_email():
    print(f"\n=== Testing Email at {datetime.now()} ===")
    msg = MIMEText("This is a test email from your fitness app")
    msg["Subject"] = "Test Email"
    msg["From"] = "shortskaraja7@gmail.com"
    msg["To"] = "nabdabop10@gmail.com"
    
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login("shortskaraja7@gmail.com", "vnbaauvtggipnbsz")
        server.send_message(msg)
        print("✅ Email sent successfully!")

if __name__ == "__main__":
    test_email()