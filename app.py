import random
import streamlit as st
from yt_extractor import get_info
import database_service as dbs
from auth import show_auth, verify_token, logout
import jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@st.cache_data
def get_workouts():
    return dbs.get_all_workouts()

def get_duration_text(duration_s):
    seconds = duration_s % 60
    minutes = int((duration_s / 60) % 60)
    hours = int((duration_s / (60*60)) % 24)
    text = ''
    if hours > 0:
        text += f'{hours:02d}:{minutes:02d}:{seconds:02d}'
    else:
        text += f'{minutes:02d}:{seconds:02d}'
    return text

def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=2)
    }
    return jwt.encode(payload, os.getenv("SECRET_KEY"), algorithm='HS256')

def main_app():
    # Authentication check
    if 'user' not in st.session_state:
        show_auth()
        st.stop()

    user = st.session_state['user']
    st.sidebar.title(f"Welcome, {user['name']}!")
    
    if st.sidebar.button("Logout"):
        logout()

    menu_options = ("Today's Workout", "All workouts", "Add workout", "Set Email Reminder")
    selection = st.sidebar.selectbox("Menu", menu_options)

    if selection == "All workouts":
        st.markdown("## All workouts")
        workouts = get_workouts()
        if not workouts:
            st.text("No workouts in Database!")
        else:
            for wo in workouts:
                url = "https://youtu.be/" + wo["video_id"]
                st.text(wo['title'])
                st.text(f"{wo['channel']} - {get_duration_text(wo['duration'])}")
                
                if st.button('Delete workout', key=wo["video_id"]):
                    dbs.delete_workout(wo["video_id"])
                    st.cache_data.clear()
                    st.rerun()
                st.video(url)

    elif selection == "Add workout":
        st.markdown("## Add workout")
        url = st.text_input('Enter YouTube workout video URL')
        if url:
            workout_data = get_info(url)
            if workout_data is None:
                st.error("Could not fetch video details. Check the URL!")
            else:
                st.text(workout_data['title'])
                st.text(workout_data['channel'])
                st.video(url)
                if st.button("Add workout"):
                    dbs.insert_workout(workout_data)
                    st.success("Workout added successfully!")
                    st.cache_data.clear()

    elif selection == "Set Email Reminder":
        st.markdown("## Email Reminder Setup")

        # Use logged-in user's email by default
        email = st.text_input("Email", value=user['email'])
        
        existing_schedule = dbs.get_schedule_by_email(email) if email else None
        
        col1, col2 = st.columns(2)
        with col1:
            default_hour = existing_schedule[0]['time'].split(':')[0] if existing_schedule else 12
            hour = st.number_input("Hour (0-23)", min_value=0, max_value=23, value=int(default_hour))
        with col2:
            default_minute = existing_schedule[0]['time'].split(':')[1] if existing_schedule else 0
            minute = st.number_input("Minute (0-59)", min_value=0, max_value=59, value=int(default_minute))
        
        schedule_time = f"{hour:02d}:{minute:02d}"

        workouts = get_workouts()
        if not workouts:
            st.warning("No workouts in the database!")
        else:
            workout_options = {f"{wo['title']} ({wo['channel']})": wo["video_id"] for wo in workouts}
            
            default_workout = next(
                (k for k,v in workout_options.items() 
                if existing_schedule and v == existing_schedule[0]['video_id']),
                list(workout_options.keys())[0]
            )
            
            selected_workout = st.selectbox(
                "Choose a workout:", 
                options=list(workout_options.keys()),
                index=list(workout_options.keys()).index(default_workout) if existing_schedule else 0
            )
            video_id = workout_options[selected_workout]
            
            if email and schedule_time and video_id:
                workout = dbs.get_workout_by_id(video_id)[0]
                data = {
                    "email": email,
                    "time": schedule_time,
                    "video_id": video_id,
                    "title": workout['title'],
                    "channel": workout['channel'],
                    "duration": workout['duration'],
                    "user_id": user['user_id']  # Link reminder to user
                }
                
                if existing_schedule:
                    if st.button("Update Reminder"):
                        dbs.update_schedule(email, schedule_time, video_id)
                        st.success(f"Updated reminder for {email} at {schedule_time}!")
                else:
                    if st.button("Set Reminder"):
                        dbs.insert_schedule(data)
                        st.success(f"Reminder set for {selected_workout} at {schedule_time}!")

    else:  # Today's Workout
        st.markdown("## Today's Workout")
        workouts = get_workouts()
        if not workouts:
            st.text("No workouts in Database!")
        else:
            wo = dbs.get_workout_today()
            if not wo:
                idx = random.randint(0, len(workouts)-1)
                wo = workouts[idx]
                dbs.update_workout_today(wo, insert=True)
            else:
                wo = wo[0]
            
            if st.button("Choose another workout"):
                if len(workouts) > 1:
                    new_wo = random.choice([w for w in workouts if w['video_id'] != wo['video_id']])
                    dbs.update_workout_today(new_wo)
                    st.rerun()
            
            url = "https://youtu.be/" + wo["video_id"]
            st.text(wo['title'])
            st.text(f"{wo['channel']} - {get_duration_text(wo['duration'])}")
            st.video(url)

if __name__ == "__main__":
    main_app()