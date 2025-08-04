import streamlit as st
from auth import AuthService
from auth import auth_service
from database_service import dbs
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from yt_extractor import yt_extractor
import time
import re

auth_service = AuthService(dbs_service=dbs)  # Now AuthService is defined
auth_service.dbs = dbs  # Ensure DB connection
load_dotenv()  # Load environment variables

# =====================================================================
# 1. CRITICAL OAUTH INITIALIZATION (Must be at the VERY TOP)
# =====================================================================
st.components.v1.html(
    """
<script>
    // Unified message handler for all OAuth events
    window.addEventListener('message', (event) => {
        // Debug all OAuth state messages
        if (event.data.type && event.data.type.startsWith('oauth_')) {
            console.group('[OAuth] Message');
            console.log('Type:', event.data.type);
            console.log('Data:', event.data);
            console.groupEnd();
        }
    });

    // Robust iframe permission fix
    function fixFramePermissions() {
        try {
            const frame = window.frameElement;
            if (frame) {
                // Set both 'allow' and 'sandbox' attributes
                frame.setAttribute('allow', 'same-origin; scripts; storage-access-by-user-activation');
                frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-storage-access-by-user-activation');
                console.log('Frame permissions updated');
            }
        } catch(e) {
            console.warn('Permission adjustment:', e);
        }
    }

    // Run on load and retry periodically
    fixFramePermissions();
    setInterval(fixFramePermissions, 3000);
</script>
""",
    height=0,
)

# =====================================================================
# 2. OAUTH CALLBACK HANDLER (Must come before other app logic)
# =====================================================================
if "code" in st.query_params:
    if "state" not in st.query_params:
        st.error(
            """
        ❌ Missing state parameter - Possible solutions:
        1. Ensure Google Cloud Console has exact redirect URI: http://localhost:8501/
        2. Check browser isn't stripping URL parameters
        3. Verify no ad-blockers are interfering
        """
        )
        st.stop()

    try:
        auth_service._handle_auth_callback()
        st.rerun()
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        st.stop()

# Session state initialization
if "oauth_state" not in st.session_state:
    st.session_state.oauth_state = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None


# Utility Functions
@st.cache_data(ttl=300)
def get_workouts():
    """Get workouts with guaranteed video URLs"""
    try:
        workouts = dbs.get_all_workouts_with_urls()
        if not workouts:
            st.warning("No workouts found in database")
        return workouts
    except Exception as e:
        st.error(f"Failed to load workouts: {str(e)}")
        return []


def get_duration_text(duration_s):
    seconds = duration_s % 60
    minutes = int(duration_s / 60 % 60)
    hours = int(duration_s / 3600 % 24)
    return (
        f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        if hours > 0
        else f"{minutes:02d}:{seconds:02d}"
    )


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None


def display_workout(wo):
    """Enhanced workout display with fallbacks"""
    if not wo or "video_id" not in wo:
        st.error("Invalid workout data")
        return None

    try:
        # Use pre-formatted URL if available, otherwise construct
        url = wo.get("video_url", f'https://youtu.be/{wo["video_id"]}')

        col1, col2 = st.columns([4, 1])
        with col1:
            st.subheader(wo.get("title", "Untitled Workout"))
            st.caption(
                f"{wo.get('channel', 'Unknown channel')} • {get_duration_text(wo.get('duration', 0))}"
            )
            st.video(url)

        return url
    except Exception as e:
        st.error(f"Display error: {str(e)}")
        return None


# App Sections
def all_workouts_section():
    st.markdown("## All Workouts")
    workouts = dbs.get_all_workouts_with_urls()

    if not workouts:
        st.info("No workouts available!")
        return

    for wo in workouts:
        if not wo or "video_id" not in wo:
            st.warning("Invalid workout format - skipping")
            continue

        col1, col2 = st.columns([4, 1])

        with col1:
            url = wo.get("video_url", f"https://youtu.be/{wo['video_id']}")
            st.subheader(wo.get("title", "Untitled Workout"))
            st.caption(
                f"{wo.get('channel', 'Unknown')} • {get_duration_text(wo.get('duration', 0))}"
            )
            st.video(url)

        with col2:
            if st.button("Delete", key=f"del_{wo['video_id']}"):
                # Add confirmation dialog
                if st.session_state.get("confirm_delete") == wo["video_id"]:
                    if dbs.delete_workout(wo["video_id"]):
                        st.cache_data.clear()
                        st.success("✅ Deleted!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Deletion failed. Check logs.")
                    del st.session_state["confirm_delete"]
                else:
                    st.session_state["confirm_delete"] = wo["video_id"]
                    st.warning("Click Delete again to confirm")


def add_workout_section():
    st.markdown("## Add Workout")
    url = st.text_input("Enter YouTube workout video URL")

    if url:
        try:
            workout_data = yt_extractor.get_info(url)
            if workout_data is None:
                st.error("Could not fetch video details. Check the URL!")
            else:
                st.text(workout_data["title"])
                st.text(workout_data["channel"])
                st.video(url)

                if st.button("Add Workout"):
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
    st.markdown("## Email Reminder Setup")
    email = st.text_input("Email", value=user["email"])

    if email and not validate_email(email):
        st.error("Please enter a valid email address")
        return

    existing_schedule = dbs.get_schedule_by_email(email) if email else None

    col1, col2 = st.columns(2)
    with col1:
        default_hour = (
            existing_schedule["time"].split(":")[0] if existing_schedule else 12
        )
        hour = st.number_input(
            "Hour (0-23)", min_value=0, max_value=23, value=int(default_hour)
        )
    with col2:
        default_minute = (
            existing_schedule["time"].split(":")[1] if existing_schedule else 0
        )
        minute = st.number_input(
            "Minute (0-59)", min_value=0, max_value=59, value=int(default_minute)
        )

    schedule_time = f"{hour:02d}:{minute:02d}"

    workouts = dbs.get_all_workouts()
    if not workouts:
        st.warning("No workouts available! Add some first.")
        return

    workout_options = {
        f"{wo['title']} ({wo['channel']})": wo["video_id"] for wo in workouts
    }
    default_idx = 0

    if existing_schedule:
        try:
            default_idx = list(workout_options.values()).index(
                existing_schedule["video_id"]
            )
        except ValueError:
            pass

    selected_workout = st.selectbox(
        "Choose a workout:", options=list(workout_options.keys()), index=default_idx
    )
    video_id = workout_options[selected_workout]
    workout = dbs.get_workout_by_id(video_id)

    if not workout:
        st.error("Selected workout not found in database!")
        return

    st.markdown("### Workout Preview")
    st.video(f"https://youtu.be/{video_id}")

    button_label = "Save Reminder" if existing_schedule else "Set Reminder"
    if st.button(button_label, key=f"reminder_btn_{user['user_id']}"):
        try:
            success = dbs.save_schedule(
                email,
                {
                    "video_id": video_id,
                    "time": schedule_time,
                    "title": workout["title"],
                    "channel": workout["channel"],
                    "duration": workout["duration"],
                    "user_id": user["user_id"],
                },
            )

            if success:
                st.success("✅ Reminder saved successfully!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Failed to save reminder")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")


def todays_workout_section():
    st.markdown("## Today's Workout Selection")
    all_workouts = get_workouts()
    current_workout = dbs.get_todays_workout()

    if not all_workouts:
        st.info("No workouts available! Add some first.")
        return

    workout_options = {
        f"{wo['title']} ({wo['channel']})": wo["video_id"] for wo in all_workouts
    }
    default_idx = 0

    if current_workout and "video_id" in current_workout:
        try:
            default_idx = list(workout_options.values()).index(
                current_workout["video_id"]
            )
        except ValueError:
            default_idx = 0

    selected = st.selectbox(
        "Choose today's workout:",
        options=list(workout_options.keys()),
        index=default_idx,
    )
    video_id = workout_options[selected]
    workout = next((wo for wo in all_workouts if wo["video_id"] == video_id), None)

    if workout:
        st.markdown("### Workout Preview")
        display_workout(workout)
    else:
        st.error("Selected workout not found!")

    if st.button("Set as Today's Workout"):
        success, message = dbs.set_todays_workout(video_id)
        if success:
            st.success(message)
            st.rerun()
        else:
            st.error(f"Failed: {message}")

    if current_workout:
        st.markdown("---")
        st.markdown("### Currently Selected Workout")
        display_workout(current_workout)


# Main App Flow
def main_app():
    # Handle authentication
    if not st.session_state.get("authenticated", False):
        auth_service.show_auth()
        st.stop()

    # Main app logic for authenticated users
    user = st.session_state.get("user", {})
    if not user:
        st.error("User session not found. Please log in again.")
        logout()  # This will handle the cleanup
        st.stop()  # No need for rerun() since logout() handles it

    # Enhanced sidebar with logout
    st.sidebar.title(f"👋 Welcome, {user.get('full_name', 'User')}!")

    # Add visual separation and confirmation
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", key="logout_btn"):
        if st.sidebar.checkbox(
            "Are you sure you want to logout?", key="logout_confirm"
        ):
            logout()  # No need for rerun() here either
        else:
            st.sidebar.warning("Logout cancelled")

    # Rest of your menu remains unchanged
    menu_options = {
        "Today's Workout": todays_workout_section,
        "All Workouts": all_workouts_section,
        "Add Workout": add_workout_section,
        "Set Email Reminder": lambda: email_reminder_section(user),
    }

    selection = st.sidebar.selectbox("Menu", list(menu_options.keys()))
    menu_options[selection]()


if __name__ == "__main__":
    main_app()
