import streamlit as st
from auth import auth_service, logout
from database_service import dbs
from yt_extractor import yt_extractor
import time
import re
import os
from dotenv import load_dotenv

import logging


@st.cache_data(ttl=5)  # Short cache for debugging
def debug_user_lookup(email: str):
    """Temporary debug function"""
    user = dbs.get_user_by_email(email)
    print(f"\nDEBUG USER LOOKUP: {user}")
    return user


logging.basicConfig(level=logging.DEBUG)

# Initialize services
load_dotenv()
auth_service.dbs = dbs


# ADD AT THE VERY TOP OF YOUR APP (before other routes)
if st.secrets.get("nuclear_debug") == "enabled":
    print("\n💣💣💣 NUCLEAR DEBUG ACTIVATED 💣💣💣")

    # Bypass all Streamlit logic
    from auth import auth_service
    from database_service import dbs
    import bcrypt

    # 1. Manual password update
    email = "nabdabop10@gmail.com"
    new_pass = "NuclearPass123!"  # Change this each test
    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()

    # 2. Direct database assault
    conn = dbs.get_connection()
    cursor = conn.cursor()

    # 3. Execute RAW SQL with verification
    print(
        f"\n🚀 EXECUTING: UPDATE users SET password_hash='{hashed[:30]}...' WHERE email='{email}'"
    )
    cursor.execute(
        "UPDATE users SET password_hash = %s WHERE email = %s", (hashed, email)
    )
    conn.commit()

    # 4. Immediate verification
    cursor.execute("SELECT password_hash FROM users WHERE email = %s", (email,))
    result = cursor.fetchone()[0]
    print(f"🔍 DATABASE STATE: {result[:60]}...")
    print(f"✅ {'MATCH' if result == hashed else '❌ MISMATCH'}")

    # 5. Force quit to prevent Streamlit interference
    import os

    os._exit(1)

# =============================================
# PASSWORD RESET HANDLER (MUST BE FIRST)
# =============================================
# =============================================
# PASSWORD RESET HANDLER (MUST BE FIRST)
# =============================================
if "token" in st.query_params and st.query_params.get("reset") == "true":
    token = st.query_params["token"]
    st.query_params.clear()  # Clear immediately

    # FORCE DEBUG OUTPUT
    print("\n⚡⚡⚡ RESET FLOW TRIGGERED ⚡⚡⚡")
    print(f"Token: {token[:50]}...")

    with st.form("reset_form"):
        new_pass = st.text_input("New Password", type="password")
        confirm_pass = st.text_input("Confirm Password", type="password")

        if st.form_submit_button("Update Password"):
            print(f"\n🔑 USER INPUT: {new_pass[:2]}... (length: {len(new_pass)})")

            if new_pass != confirm_pass:
                st.error("Passwords don't match!")
            else:
                # Generate hash with debug
                hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                print(f"🔑 HASHED VERSION: {hashed[:60]}...")

                # Nuclear update
                if auth_service.reset_password(token, new_pass):
                    print("\n🎉 RESET SUCCESSFUL - VERIFYING LOGIN")
                    # Immediate test
                    test_result = auth_service.verify_password(
                        "nabdabop10@gmail.com", new_pass
                    )
                    print(f"🧪 LOGIN TEST RESULT: {test_result}")

                    st.success("Password updated!")
                    st.session_state.clear()
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("Reset failed")

# Handle email verification tokens
if "token" in st.query_params:
    if auth_service.verify_email_token(st.query_params["token"]):
        st.success("✅ Email verified!")
    else:
        st.error("❌ Invalid token.")
    st.query_params.clear()
    st.rerun()

# =============================================
# INITIALIZATION
# =============================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None

if "show_reset" not in st.session_state:
    st.session_state.show_reset = False
if "reset_requested" not in st.session_state:
    st.session_state.reset_requested = False


# =============================================
# UTILITY FUNCTIONS
# =============================================
@st.cache_data(ttl=300)
def get_workouts():
    """Get workouts with video URLs"""
    try:
        workouts = dbs.get_all_workouts_with_urls()
        return workouts or []
    except Exception as e:
        st.error(f"Error loading workouts: {str(e)}")
        return []


def get_duration_text(duration_s):
    """Convert seconds to HH:MM:SS or MM:SS"""
    mins, secs = divmod(duration_s, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def validate_gmail(email: str) -> bool:
    """Strict Gmail validation"""
    return bool(re.match(r"^[\w\.-]+@gmail\.com$", email))


# =============================================
# APP SECTIONS
# =============================================
def all_workouts_section():
    st.markdown("## All Workouts")
    workouts = get_workouts()

    if not workouts:
        st.info("No workouts available!")
        return

    for wo in workouts:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.video(wo.get("video_url", f"https://youtu.be/{wo['video_id']}"))
            st.caption(
                f"{wo.get('title', 'Untitled')} • {wo.get('channel', 'Unknown')}"
            )
        with col2:
            if st.button("Delete", key=f"del_{wo['video_id']}"):
                if dbs.delete_workout(wo["video_id"]):
                    st.rerun()


def add_workout_section():
    st.markdown("## Add Workout")
    url = st.text_input("YouTube Video URL")

    if url:
        try:
            workout = yt_extractor.get_info(url)
            if workout:
                st.video(url)
                if st.button("Add") and dbs.add_workout(workout)[0]:
                    st.rerun()
        except Exception as e:
            st.error(f"Error processing video: {str(e)}")


def email_reminder_section(user):
    st.markdown("## Email Reminder")
    email = st.text_input("Email", value=user["email"])

    if not validate_gmail(email):
        st.error("Only @gmail.com addresses allowed")
        return

    col1, col2 = st.columns(2)
    with col1:
        hour = st.number_input("Hour", 0, 23, 12)
    with col2:
        minute = st.number_input("Minute", 0, 59, 0)
    schedule_time = f"{hour:02d}:{minute:02d}"

    workouts = dbs.get_all_workouts()
    if workouts:
        workout = st.selectbox(
            "Choose Workout",
            workouts,
            format_func=lambda x: f"{x['title']} ({x['channel']})",
        )
        st.video(f"https://youtu.be/{workout['video_id']}")

        if st.button("Save Reminder"):
            if dbs.save_schedule(
                email,
                {
                    "video_id": workout["video_id"],
                    "time": schedule_time,
                    "title": workout["title"],
                    "user_id": user["user_id"],
                },
            ):
                st.rerun()


# =============================================
# MAIN APP FLOW
# =============================================
def main_app():

    if st.sidebar.button("🛑 DEBUG: Check Password Hash"):
        if st.session_state.get("user"):
            email = st.session_state.user["email"]
            debug_user_lookup(email)
            st.rerun()
    # Authentication check
    if not st.session_state.authenticated:
        auth_service.show_auth()
        st.stop()

    user = st.session_state.user
    if not user:
        logout()
        st.stop()

    # Sidebar
    st.sidebar.title(f"👋 {user.get('full_name', 'User')}")
    if st.sidebar.button("🚪 Logout"):
        logout()

    # Main content
    menu = {
        "Today's Workout": lambda: todays_workout_ui(),
        "All Workouts": all_workouts_section,
        "Add Workout": add_workout_section,
        "Set Reminder": lambda: email_reminder_section(user),
    }
    menu[st.sidebar.selectbox("Menu", menu.keys())]()


def todays_workout_ui():
    st.markdown("## Today's Workout")
    workouts = get_workouts()

    if workouts:
        selected = st.selectbox(
            "Choose Workout",
            workouts,
            format_func=lambda x: f"{x['title']} ({x['channel']})",
        )
        st.video(f"https://youtu.be/{selected['video_id']}")

        if st.button("Set as Today's Workout"):
            if dbs.set_todays_workout(selected["video_id"])[0]:
                st.rerun()


if __name__ == "__main__":
    main_app()
