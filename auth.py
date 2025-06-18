import re
import requests
import streamlit as st
import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import database_service as dbs

# Load environment variables
load_dotenv()

# Auth0 configuration
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
SECRET_KEY = os.getenv("SECRET_KEY")

def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload['user_id']
    except Exception as e:
        st.error(f"Token verification failed: {str(e)}")
        return None

def verify_password(stored_hash, provided_password):
    """Verify hashed password against provided password"""
    try:
        return bcrypt.checkpw(provided_password.encode(), stored_hash.encode())
    except Exception as e:
        st.error(f"Password verification failed: {str(e)}")
        return False

def google_auth():
    try:
        auth_url = (
            f"https://{AUTH0_DOMAIN}/authorize?"
            f"response_type=code&"
            f"client_id={AUTH0_CLIENT_ID}&"
            f"redirect_uri=http://localhost:8501&"
            f"scope=openid%20profile%20email&"
            f"connection=google-oauth2&"
            f"prompt=login&"
            f"audience=https://{AUTH0_DOMAIN}/userinfo"
        )
        
        if st.button("Continue with Google"):
            st.markdown(f'<meta http-equiv="refresh" content="0; url={auth_url}">', 
                       unsafe_allow_html=True)
            st.stop()

        if 'code' in st.query_params:
            code = st.query_params['code'][0]
            token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            token_response = requests.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": AUTH0_CLIENT_ID,
                    "client_secret": AUTH0_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": "http://localhost:8501",
                    "audience": f"https://{AUTH0_DOMAIN}/userinfo"
                },
                headers=headers
            )
            
            token_response.raise_for_status()
            token_data = token_response.json()
            
            # Handle Google user creation/login
            user_info = requests.get(
                "https://{AUTH0_DOMAIN}/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"}
            ).json()
            
            email = user_info['email']
            name = user_info.get('name', email.split('@')[0])
            
            # Check if user exists
            user = dbs.get_user_by_email(email)
            if not user:
                # Register new Google user
                success, user = dbs.register_user(
                    email=email,
                    password=None,  # No password for Google auth
                    full_name=name,
                    google_id=user_info['sub']
                )
                if not success:
                    st.error("Failed to create Google account")
                    return
            
            # Set session
            st.session_state.update({
                'token': generate_token(user['user_id']),
                'user': {
                    'user_id': user['user_id'],
                    'email': user['email'],
                    'full_name': user['full_name'],
                    'google_id': user.get('google_id')
                }
            })
            st.rerun()

    except Exception as e:
        st.error(f"Google authentication failed: {str(e)}")

def email_auth():
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            try:
                user = dbs.get_user_by_email(email)
                
                # Check if user exists and has user_id
                if not user:
                    st.error("User not found")
                    return
                    
                if 'user_id' not in user:
                    st.error("Account configuration error - missing user ID")
                    return
                
                # Verify password
                if verify_password(user['password_hash'], password):
                    st.session_state.update({
                        'token': generate_token(user['user_id']),
                        'user': {
                            'user_id': user['user_id'],
                            'email': user['email'],
                            'full_name': user['full_name']
                        }
                    })
                    st.rerun()
                else:
                    st.error("Invalid credentials")
                    
            except Exception as e:
                st.error(f"Login failed: {str(e)}")

def register_form():
    with st.form("register_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        
        if st.form_submit_button("Register"):
            # 1. First check email format
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                st.error("Invalid email format")
                return
                
            # 2. Then check password length
            if len(password) < 8:
                st.error("Password must be at least 8 characters")
                return
                
            # 3. Then check password match
            if password != confirm:
                st.error("Passwords don't match")
                return
                
            # If all validations pass, proceed with registration
            try:
                success, result = dbs.register_user(
                    email=email,
                    password=password,
                    full_name=name
                )
                if success:
                    st.success("Registration successful! Please login.")
                else:
                    st.error(result)
            except Exception as e:
                st.error(f"Registration failed: {str(e)}")
def logout():
    st.session_state.clear()
    st.rerun()

def show_auth():
    st.title("Welcome to Fitness App")
    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Continue with Google"])
    
    with tab1:
        email_auth()
    
    with tab2:
        register_form()
    
    with tab3:
        google_auth()

def check_authentication():
    """Middleware to verify authentication"""
    if 'user' not in st.session_state:
        show_auth()
        st.stop()