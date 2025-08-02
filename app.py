import random
import streamlit as st
from yt_extractor import yt_extractor
from database_service import dbs
from auth import show_auth, logout
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from authlib.integrations.requests_client import OAuth2Session
import requests
import uuid

load_dotenv()

# Auth0 Configuration
AUTH0_CLIENT_ID = os.getenv('AUTH0_CLIENT_ID')
AUTH0_CLIENT_SECRET = os.getenv('AUTH0_CLIENT_SECRET')
AUTH0_DOMAIN = 'dev-1cs4x3qaxbgw74q4.us.auth0.com'
REDIRECT_URI = 'http://localhost:8501/auth/callback'
AUTH0_AUDIENCE = os.getenv('AUTH0_AUDIENCE')

# Initialize session state
if 'oauth_state' not in st.session_state:
    st.session_state.oauth_state = None
if 'auth_initiated' not in st.session_state:
    st.session_state.auth_initiated = False
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user' not in st.session_state:
    st.session_state.user = None

def handle_auth_callback():
    """Handle OAuth callback from Auth0"""
    print("🔄 Handling Auth0 callback...")
    
    # Modern Streamlit query param handling
    code = st.query_params.get("code")
    state = st.query_params.get("state")
    
    if not code:
        st.error("❌ Missing authorization code")
        print("Query params:", dict(st.query_params))
        return
    
    if state != st.session_state.oauth_state:
        st.error("❌ Invalid state parameter")
        print(f"Expected: {st.session_state.oauth_state}, Got: {state}")
        return

    try:
        client = OAuth2Session(
            AUTH0_CLIENT_ID,
            AUTH0_CLIENT_SECRET,
            redirect_uri=REDIRECT_URI
        )
        
        token = client.fetch_token(
            f"https://{AUTH0_DOMAIN}/oauth/token",
            code=code,
            grant_type='authorization_code'
        )
        
        userinfo = requests.get(
            f"https://{AUTH0_DOMAIN}/userinfo",
            headers={'Authorization': f"Bearer {token['access_token']}"}
        ).json()
        
        print("🟢 User info:", userinfo)
        
        st.session_state.update({
            'token': token,
            'user': {
                'user_id': userinfo.get('sub'),
                'email': userinfo.get('email'),
                'full_name': userinfo.get('name', userinfo.get('nickname', 'User'))
            },
            'authenticated': True
        })
        
        st.query_params.clear()
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Authentication failed: {str(e)}")
        print(f"🔴 Error: {repr(e)}")
        logout()

@st.cache_data(ttl=300)
def get_workouts():
    """Fetch all workouts with caching"""
    try:
        return dbs.get_all_workouts()
    except Exception as e:
        st.error(f"Failed to load workouts: {str(e)}")
        return []

def get_duration_text(duration_s):
    """Convert seconds to HH:MM:SS format"""
    seconds = duration_s % 60
    minutes = int(duration_s / 60 % 60)
    hours = int(duration_s / 3600 % 24)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"

def display_workout(wo):
    """Display workout video and info"""
    if not wo or 'video_id' not in wo or not wo['video_id']:
        st.error('Invalid workout data: missing video ID')
        return None
    
    try:
        url = 'https://youtu.be/' + wo['video_id']
        st.subheader(wo.get('title', 'Untitled Workout'))
        st.caption(f"{wo.get('channel', 'Unknown channel')} - {get_duration_text(wo.get('duration', 0))}")
        st.video(url)
        return url
    except Exception as e:
        st.error(f"Error displaying workout: {str(e)}")
        return None

def all_workouts_section():
    """Display all workouts with delete options"""
    st.markdown('## All Workouts')
    workouts = get_workouts()
    
    if not workouts:
        st.info('No workouts available in the database!')
        return
    
    for wo in workouts:
        if wo and wo.get('video_id'):
            url = display_workout(wo)
            if url and st.button('Delete workout', key=f"del_{wo['video_id']}"):
                if dbs.delete_workout(wo['video_id']):
                    st.cache_data.clear()
                    st.success('Workout deleted successfully!')
                    st.rerun()
                else:
                    st.error('Failed to delete workout')
        else:
            st.warning('Skipping invalid workout entry')

def add_workout_section():
    """Add new workout from YouTube URL"""
    st.markdown('## Add Workout')
    url = st.text_input('Enter YouTube workout video URL')
    
    if url:
        try:
            workout_data = yt_extractor.get_info(url)
            if workout_data is None:
                st.error('Could not fetch video details. Check the URL!')
            else:
                st.text(workout_data['title'])
                st.text(workout_data['channel'])
                st.video(url)
                
                if st.button('Add Workout'):
                    success, message = dbs.add_workout(workout_data)
                    if success:
                        st.success(message)
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(message)
        except Exception as e:
            st.error(f"Error processing video: {str(e)}")

def email_reminder_section(user):
    """Setup email reminders"""
    st.markdown('## Email Reminder Setup')
    email = st.text_input('Email', value=user['email'])
    existing_schedule = dbs.get_schedule_by_email(email) if email else None
    
    col1, col2 = st.columns(2)
    with col1:
        default_hour = existing_schedule['time'].split(':')[0] if existing_schedule and 'time' in existing_schedule else 12
        hour = st.number_input('Hour (0-23)', min_value=0, max_value=23, value=int(default_hour))
    with col2:
        default_minute = existing_schedule['time'].split(':')[1] if existing_schedule and 'time' in existing_schedule else 0
        minute = st.number_input('Minute (0-59)', min_value=0, max_value=59, value=int(default_minute))
    
    schedule_time = f"{hour:02d}:{minute:02d}"
    workouts = get_workouts()
    
    if not workouts:
        st.warning('No workouts in the database!')
    else:
        workout_options = {f"{wo['title']} ({wo['channel']})": wo['video_id'] for wo in workouts}
        default_idx = 0
        
        if existing_schedule and 'video_id' in existing_schedule:
            try:
                default_idx = list(workout_options.values()).index(existing_schedule['video_id'])
            except ValueError:
                default_idx = 0
                
        selected_workout = st.selectbox(
            'Choose a workout:',
            options=list(workout_options.keys()),
            index=default_idx
        )
        video_id = workout_options[selected_workout]
        
        if email and schedule_time and video_id:
            workout = dbs.get_workout_by_id(video_id)
            if not workout:
                st.error('Selected workout not found in database!')
                return
                
            data = {
                'email': email,
                'time': schedule_time,
                'video_id': video_id,
                'title': workout['title'],
                'channel': workout['channel'],
                'duration': workout['duration'],
                'user_id': user['user_id']
            }
            
            if existing_schedule:
                if st.button('Update Reminder'):
                    if dbs.save_schedule(email, data):
                        st.success(f"Updated reminder for {email} at {schedule_time}!")
                    else:
                        st.error('Failed to update reminder')
            elif st.button('Set Reminder'):
                if dbs.save_schedule(email, data):
                    st.success(f"Reminder set for {selected_workout} at {schedule_time}!")
                else:
                    st.error('Failed to set reminder')

def todays_workout_section():
    """Select today's workout"""
    st.markdown("## Today's Workout Selection")
    all_workouts = get_workouts()
    current_workout = dbs.get_todays_workout()
    
    if not all_workouts:
        st.info('No workouts available! Add some first.')
        return
        
    workout_options = {f"{wo['title']} ({wo['channel']})": wo['video_id'] for wo in all_workouts}
    default_idx = 0
    
    if current_workout and 'video_id' in current_workout:
        try:
            default_idx = list(workout_options.values()).index(current_workout['video_id'])
        except ValueError:
            default_idx = 0
            
    selected = st.selectbox(
        "Choose today's workout:",
        options=list(workout_options.keys()),
        index=default_idx
    )
    video_id = workout_options[selected]
    workout = next((wo for wo in all_workouts if wo['video_id'] == video_id), None)
    
    if workout:
        st.markdown('### Workout Preview')
        display_workout(workout)
    else:
        st.error('Selected workout not found!')
        
    if st.button("Set as Today's Workout"):
        success, message = dbs.set_todays_workout(video_id)
        if success:
            st.success(message)
            st.rerun()
        else:
            st.error(f"Failed: {message}")
            
    if current_workout:
        st.markdown('---')
        st.markdown('### Currently Selected Workout')
        display_workout(current_workout)

def main_app():
    """Main application flow"""
    if st.query_params.get('code'):
        handle_auth_callback()
        return
        
    if not st.session_state.get('authenticated', False):
        show_auth()
        st.stop()
        
    user = st.session_state.get('user', {})
    if not user:
        st.error('User session not found. Please log in again.')
        logout()
        st.stop()
        
    st.sidebar.title(f"Welcome, {user.get('full_name', 'User')}!")
    if st.sidebar.button('Logout'):
        logout()
        st.rerun()
        
    menu_options = {
        "Today's Workout": todays_workout_section,
        'All Workouts': all_workouts_section,
        'Add Workout': add_workout_section,
        'Set Email Reminder': lambda: email_reminder_section(user)
    }
    
    selection = st.sidebar.selectbox('Menu', list(menu_options.keys()))
    menu_options[selection]()

if __name__ == '__main__':
    main_app()