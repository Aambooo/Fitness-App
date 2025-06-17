import requests
import streamlit as st
import os
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import database_service as dbs

# Load environment variables
load_dotenv()

# Auth0 configuration (loaded from .env)
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
SECRET_KEY = os.getenv("SECRET_KEY")

# JWT Functions
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

# Auth0 Google Login 
def google_auth():
    try:
        # Generate Auth0 URL with PKCE (more secure)
        auth_url = (
            f"https://{AUTH0_DOMAIN}/authorize?"
            f"response_type=code&"
            f"client_id={AUTH0_CLIENT_ID}&"
            f"redirect_uri=http://localhost:8501&"
            f"scope=openid%20profile%20email&"
            f"connection=google-oauth2&"
            f"prompt=login&"
            f"audience=https://{AUTH0_DOMAIN}/userinfo"  # Add audience
        )
        
        if st.button("Continue with Google"):
            st.markdown(f'<meta http-equiv="refresh" content="0; url={auth_url}">', 
                       unsafe_allow_html=True)
            st.stop()

        if 'code' in st.query_params:
            code = st.query_params['code'][0]
            
            # Token request with proper headers and form-data
            token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            token_response = requests.post(
                token_url,
                data={  # Changed from json to data
                    "grant_type": "authorization_code",
                    "client_id": AUTH0_CLIENT_ID,
                    "client_secret": AUTH0_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": "http://localhost:8501",
                    "audience": f"https://{AUTH0_DOMAIN}/userinfo"  # Required for some Auth0 setups
                },
                headers=headers
            )
            
            # Debug output
            print(f"Token request data: {token_response.request.body}")
            print(f"Token response: {token_response.status_code} {token_response.text}")
            
            token_response.raise_for_status()
            token_data = token_response.json()
            
            # Rest of your user handling code...
            # ... [keep existing user session code]

    except requests.exceptions.HTTPError as e:
        error_details = e.response.json()
        st.error(f"""
        Auth0 Error: {error_details.get('error', 'Unknown')}
        Description: {error_details.get('error_description', 'No details')}
        """)
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")

# Email Auth
def email_auth():
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            try:
                user = dbs.get_user_by_email(email)
                if user and user['password'] == password:
                    st.session_state.update({
                        'token': generate_token(user['user_id']),
                        'user': user
                    })
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            except Exception as e:
                st.error(f"Login failed: {str(e)}")

# Registration
def register_form():
    with st.form("register_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        
        if st.form_submit_button("Register"):
            if password == confirm:
                try:
                    dbs.register_user(email, password, name)
                    st.success("Registration successful! Please login.")
                except Exception as e:
                    st.error(f"Registration failed: {str(e)}")
            else:
                st.error("Passwords don't match")

# Logout
def logout():
    st.session_state.clear()
    st.rerun()

# Main Auth UI
def show_auth():
    st.title("Welcome to Fitness App")
    
    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Continue with Google"])
    
    with tab1:
        email_auth()
    
    with tab2:
        register_form()
    
    with tab3:
        google_auth()