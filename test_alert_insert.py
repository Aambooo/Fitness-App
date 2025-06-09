from database_service import insert_alert

# Set a time in HH:MM format (24-hour), a few minutes ahead of current time
email = "nabdabop10@gmail.com"
workout_id = "1"  # Example: "dQw4w9WgXcQ"
alert_time = "17:52"  # Change this to your desired time

insert_alert(email, workout_id, alert_time)
print("Test alert inserted.")
