import random
import streamlit as st
from yt_extractor import get_info
import database_service as dbs

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

st.title("Workout App")

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

    email = st.text_input("Enter your email:")
    
    # Check if this email already has a schedule
    existing_schedule = dbs.get_schedule_by_email(email) if email else None
    
    # Time selection
    col1, col2 = st.columns(2)
    with col1:
        default_hour = existing_schedule[0]['time'].split(':')[0] if existing_schedule else 12
        hour = st.number_input("Hour (0-23)", min_value=0, max_value=23, value=int(default_hour))
    with col2:
        default_minute = existing_schedule[0]['time'].split(':')[1] if existing_schedule else 0
        minute = st.number_input("Minute (0-59)", min_value=0, max_value=59, value=int(default_minute))
    
    schedule_time = f"{hour:02d}:{minute:02d}"

    # Workout selection
    workouts = get_workouts()
    if not workouts:
        st.warning("No workouts in the database!")
    else:
        workout_options = {f"{wo['title']} ({wo['channel']})": wo["video_id"] for wo in workouts}
        
        # Set default to existing workout if available
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
                "duration": workout['duration']
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
            # Randomly select a workout if none is set
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