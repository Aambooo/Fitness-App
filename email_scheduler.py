import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import database_service as dbs

# Debug setup
print("💻 Email scheduler started at:", datetime.now().strftime("%H:%M:%S"))

def send_email(to_email, subject, body):
    print(f"\n✉️ Attempting to send email to {to_email}...")
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = "shortskaraja7@gmail.com"
        msg["To"] = to_email
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login("shortskaraja7@gmail.com", "vnba auvt ggip nbsz")
            server.send_message(msg)
        print("✅ Email sent successfully!")
        return True
    except Exception as e:
        print(f"❌ Email failed: {str(e)}")
        return False

def check_alerts():
    current_time = datetime.now().strftime("%H:%M")
    print(f"\n⏰ Checking alerts at {current_time}")
    
    # Test database connection
    try:
        schedules = dbs.get_schedules_by_time(current_time)
        print(f"🔍 Found {len(schedules)} scheduled reminders")
        
        for s in schedules:
            print(f"Processing reminder for {s['email']} (Workout: {s['title']})")
            send_email(
                s["email"],
                "⏰ Workout Reminder!",
                f"Time for your workout: {s['title']}\nWatch: https://youtu.be/{s['video_id']}"
            )
    except Exception as e:
        print(f"⚠️ Database error: {str(e)}")

# Continuous loop with error handling
while True:
    check_alerts()
    time.sleep(60 - time.time() % 60)  # Sync to whole minutes