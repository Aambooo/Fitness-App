import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import database_service as dbs

# Gmail configuration
EMAIL_ADDRESS = "shortskaraja7@gmail.com"
EMAIL_PASSWORD = "vnba auvt ggip nbsz"  

def send_email(to_email, subject, body):
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"Email sent to {to_email}")
    except Exception as e:
        print("Failed to send email:", e)

def check_and_send_alerts():
    now = datetime.now().strftime("%H:%M")  # Format: 'HH:MM'
    alerts = dbs.get_alerts_by_time(now)
    
    for alert in alerts:
        workout_id = alert["workout_id"]
        email = alert["email"]
        workouts = dbs.get_all_workouts()
        workout = next((w for w in workouts if w["video_id"] == workout_id), None)

        if workout:
            body = (
                f"Hi! 👋\n\nIt's time for your scheduled workout:\n\n"
                f"🏋️ Title: {workout['title']}\n"
                f"📺 Channel: {workout['channel']}\n"
                f"🕒 Duration: {int(workout['duration']//60)} mins\n"
                f"🔗 Link: https://youtu.be/{workout['video_id']}\n\n"
                f"Let's go! 💪"
            )
            send_email(email, "🏃 Time for Your Workout!", body)

# 🔁 Loop every 60 seconds
if __name__ == "__main__":
    while True:
        check_and_send_alerts()
        time.sleep(60)
