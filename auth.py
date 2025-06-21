import uuid
import requests
from requests.exceptions import RequestException
import streamlit as st
import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import database_service as dbs
from typing import Optional, Dict, Any


# Load environment variables
load_dotenv()

try:
    import database_service
    dbs = database_service.dbs
    
    # Add verification check HERE
    if not hasattr(dbs, 'verify_user_password'):
        st.error("❌ Database Service Error: verify_user_password missing!")
        print("CRITICAL ERROR: Missing methods in DatabaseService!")
        print("Available methods:", [m for m in dir(dbs) if not m.startswith('_')])
        st.stop()  # Halt the app if there's an issue
        
except Exception as e:
    st.error(f"Failed to initialize database: {str(e)}")
    st.stop()

# Auth0 configuration - validate env vars
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
SECRET_KEY = os.getenv("SECRET_KEY")

# Validate required environment variables
if not all([AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_DOMAIN, SECRET_KEY]):
    raise RuntimeError("Missing required environment variables for authentication")

def generate_token(user_id: str) -> str:
    """Generate JWT token for authenticated user"""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token: str) -> Optional[str]:
    """Verify JWT token and return user_id if valid"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        st.error("Session expired. Please log in again.")
    except jwt.InvalidTokenError as e:
        st.error(f"Invalid session: {str(e)}")
    except Exception as e:
        st.error(f"Token verification failed: {str(e)}")
    return None

def verify_password(email: str, password: str) -> bool:
    """Verify password using database service"""
    try:
        # Add debug output
        print(f"Debug: Trying to verify password for {email}")
        
        # Verify the dbs instance has the method
        if not hasattr(dbs, 'verify_user_password'):
            st.error("Database service configuration error!")
            print(f"Available methods: {dir(dbs)}")
            return False
            
        return dbs.verify_user_password(email, password)
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        print(f"Error details: {repr(e)}")
        return False

def show_auth():
    """Display authentication options with both email and Google login"""
    # ▼▼▼ ADD DEBUG CODE RIGHT HERE ▼▼▼ (at the VERY START of the function)
    print("\n=== AUTH DEBUG ===")
    print(f"DatabaseService instance: {id(dbs)}")
    print(f"verify_user_password exists: {hasattr(dbs, 'verify_user_password')}")
    print(f"All methods: {[m for m in dir(dbs) if not m.startswith('_')]}")
    print("=================\n")
    # ▲▲▲ END OF DEBUG CODE ▲▲▲

    st.title("Welcome to Fitness App")
    # Clear any previous errors
    if 'auth_error' in st.session_state:
        del st.session_state.auth_error
    
    # Create tabs for different auth methods
    tab1, tab2 = st.tabs(["Email Login/Register", "Continue with Google"])
    
    with tab1:
        # Email Login/Registration Form
        auth_type = st.radio("Choose action:", ["Login", "Register"], horizontal=True)
        
        with st.form("email_auth"):
            email = st.text_input("Email", placeholder="your@email.com").strip()
            
            if auth_type == "Login":
                password = st.text_input("Password", type="password")
            else:  # Registration
                col1, col2 = st.columns(2)
                with col1:
                    full_name = st.text_input("Full Name", placeholder="John Doe").strip()
                with col2:
                    password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
            
            submitted = st.form_submit_button("Login" if auth_type == "Login" else "Register")
            
            if submitted:
                if not email:
                    st.error("Email is required")
                    return
                
                if auth_type == "Login":
                    if not password:
                        st.error("Password is required")
                        return
                        
                    try:
                        if dbs.verify_user_password(email, password):
                            user = dbs.get_user_by_email(email)
                            if not user:
                                st.error("User not found")
                                return
                                
                            st.session_state.update({
                                'authenticated': True,
                                'user': {
                                    'user_id': user['user_id'],
                                    'email': user['email'],
                                    'full_name': user.get('full_name', email.split('@')[0])
                                }
                            })
                            st.rerun()
                        else:
                            st.error("Invalid email or password")
                    except Exception as e:
                        st.error(f"Login failed: {str(e)}")
                else:
                    # Registration validation
                    if not full_name:
                        st.error("Please enter your full name")
                    elif len(password) < 8:
                        st.error("Password must be at least 8 characters")
                    elif password != confirm_password:
                        st.error("Passwords don't match!")
                    else:
                        try:
                            success, message = dbs.register_user(
                                email=email,
                                password=password,
                                full_name=full_name
                            )
                            if success:
                                st.success("Registration successful! Please login.")
                            else:
                                st.error(message)
                        except Exception as e:
                            st.error(f"Registration failed: {str(e)}")
    
    with tab2:
        # Google Login Button
        if st.button("Continue with Google"):
            # Initialize auth state
            st.session_state.oauth_state = str(uuid.uuid4())
            st.session_state.auth_initiated = True
            
            auth_url = (
                f"https://{AUTH0_DOMAIN}/authorize?"
                f"response_type=code&"
                f"client_id={AUTH0_CLIENT_ID}&"
                f"redirect_uri=http://localhost:8501&"
                f"scope=openid%20profile%20email&"
                f"connection=google-oauth2&"
                f"state={st.session_state.oauth_state}&"
                f"prompt=select_account"
            )
            st.markdown(f'<meta http-equiv="refresh" content="0; url={auth_url}">', 
                      unsafe_allow_html=True)
            st.stop()

def handle_auth_callback():
    """Process the authentication callback from Google"""
    try:
        if 'state' not in st.query_params:
            st.session_state.auth_error = "Missing security parameter"
            st.rerun()
            return
            
        if st.query_params['state'] != st.session_state.get('oauth_state', ''):
            st.session_state.auth_error = "Session expired"
            st.rerun()
            return
            
    except Exception as e:
        st.session_state.auth_error = f"Authentication failed: {str(e)}"
        st.rerun()

def logout():
    """Clear session state and log user out"""
    keys_to_clear = [
        'authenticated', 
        'user',
        'oauth_state',
        'auth_initiated',
        'auth_error'
    ]
    
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    st.success("You have been successfully logged out.")
    st.rerun()

def google_auth():
    """Handle Google OAuth authentication flow"""
    try:
        # Initialize state if not exists
        if 'oauth_state' not in st.session_state:
            st.session_state.oauth_state = str(uuid.uuid4())
            st.session_state.auth_initiated = False

        # Only show button if auth hasn't been initiated
        if not st.session_state.auth_initiated:
            if st.button("Continue with Google"):
                st.session_state.auth_initiated = True
                auth_url = (
                    f"https://{AUTH0_DOMAIN}/authorize?"
                    f"response_type=code&"
                    f"client_id={AUTH0_CLIENT_ID}&"
                    f"redirect_uri=http://localhost:8501&"
                    f"scope=openid%20profile%20email&"
                    f"connection=google-oauth2&"
                    f"state={st.session_state.oauth_state}&"
                    f"prompt=select_account"
                )
                st.markdown(f'<meta http-equiv="refresh" content="0; url={auth_url}">', 
                          unsafe_allow_html=True)
                st.stop()

        # Handle callback
        if 'code' in st.query_params:
            if not st.session_state.get('auth_initiated', False):
                st.error("Invalid request. Please click the button again.")
                if 'oauth_state' in st.session_state:
                    del st.session_state.oauth_state
                st.session_state.auth_initiated = False
                st.rerun()
                return

            if 'state' not in st.query_params:
                st.error("Missing security parameter. Please try again.")
                st.session_state.auth_initiated = False
                st.rerun()
                return

            if st.query_params['state'] != st.session_state.oauth_state:
                st.error("Session expired. Please click the button again.")
                st.session_state.auth_initiated = False
                st.rerun()
                return

            # Exchange code for token
            code = st.query_params['code']
            token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
            
            try:
                token_response = requests.post(
                    token_url,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Cache-Control": "no-cache"
                    },
                    data={
                        "grant_type": "authorization_code",
                        "client_id": AUTH0_CLIENT_ID,
                        "client_secret": AUTH0_CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": "http://localhost:8501"
                    },
                    timeout=10
                )
                token_response.raise_for_status()
                token_data = token_response.json()
                
            except RequestException as e:
                st.error("Authentication service unavailable. Please try later.")
                print(f"Token exchange error: {str(e)}")
                if hasattr(e, 'response'):
                    print(f"Response: {e.response.text}")
                st.session_state.auth_initiated = False
                st.rerun()
                return

            # Get user info
            try:
                user_info = requests.get(
                    f"https://{AUTH0_DOMAIN}/userinfo",
                    headers={
                        "Authorization": f"Bearer {token_data['access_token']}",
                        "Accept": "application/json"
                    },
                    timeout=5
                ).json()
                
                if 'error' in user_info:
                    raise ValueError(user_info['error'])
                    
            except Exception as e:
                st.error("Failed to load user profile")
                print(f"Userinfo error: {str(e)}")
                st.session_state.auth_initiated = False
                st.rerun()
                return

            # Process user data
            email = user_info.get('email')
            if not email:
                st.error("No email found in user profile")
                st.session_state.auth_initiated = False
                st.rerun()
                return
                
            name = user_info.get('name', email.split('@')[0])
            google_id = user_info.get('sub')
            
            # Find or create user
            try:
                user = dbs.get_user_by_email(email)
                if not user:
                    print(f"Registering new Google user: {email}")
                    success, result = dbs.register_user(
                        email=email,
                        password=None,
                        full_name=name,
                        google_id=google_id
                    )
                    if not success:
                        st.error(f"Account creation failed: {result}")
                        st.session_state.auth_initiated = False
                        st.rerun()
                        return
                    user = dbs.get_user_by_email(email)

                # Create session
                st.session_state.update({
                    'authenticated': True,
                    'user': {
                        'user_id': user['user_id'],
                        'email': user['email'],
                        'full_name': user.get('full_name', name),
                        'google_id': google_id
                    }
                })
                
                # Clean up
                keys_to_remove = ['oauth_state', 'auth_initiated']
                for key in keys_to_remove:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.rerun()
                
            except Exception as e:
                st.error(f"Failed to process user: {str(e)}")
                st.session_state.auth_initiated = False
                st.rerun()
                return

    except Exception as e:
        st.error("Authentication process failed")
        print(f"Auth error: {str(e)}")
        # Clear all auth-related session state
        keys_to_remove = ['oauth_state', 'auth_initiated']
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()