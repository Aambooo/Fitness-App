import uuid
import requests
from requests.exceptions import RequestException
import streamlit as st
from streamlit.components.v1 import html
import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import database_service as dbs
from typing import Optional, Dict, Any
import webbrowser
from authlib.integrations.requests_client import OAuth2Session

load_dotenv()
REDIRECT_URI = 'http://localhost:8501/auth/callback'

class AuthService:
    def __init__(self):
        self.init_database_service()
        self.validate_auth0_config()
        self.oauth_client = OAuth2Session(
            client_id=self.AUTH0_CLIENT_ID,
            client_secret=self.AUTH0_CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope="openid profile email"
        )

    def init_database_service(self):
        try:
            import database_service
            dbs = database_service.dbs
            if not hasattr(dbs, 'verify_user_password'):
                st.error('❌ Database Service Error: verify_user_password missing!')
                print('CRITICAL ERROR: Missing methods in DatabaseService!')
                print('Available methods:', [m for m in dir(dbs) if not m.startswith('_')])
                st.stop()
            self.dbs = dbs
        except Exception as e:
            st.error(f"Failed to initialize database: {str(e)}")
            st.stop()

    def validate_auth0_config(self):
        required_vars = {
            'AUTH0_CLIENT_ID': os.getenv('AUTH0_CLIENT_ID'),
            'AUTH0_CLIENT_SECRET': os.getenv('AUTH0_CLIENT_SECRET'),
            'AUTH0_DOMAIN': os.getenv('AUTH0_DOMAIN'),
            'SECRET_KEY': os.getenv('SECRET_KEY'),
            'AUTH0_AUDIENCE': os.getenv('AUTH0_AUDIENCE')
        }
        missing_vars = [k for (k, v) in required_vars.items() if not v]
        
        if missing_vars:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        self.AUTH0_CLIENT_ID = required_vars['AUTH0_CLIENT_ID']
        self.AUTH0_CLIENT_SECRET = required_vars['AUTH0_CLIENT_SECRET']
        self.AUTH0_DOMAIN = required_vars['AUTH0_DOMAIN']
        self.SECRET_KEY = required_vars['SECRET_KEY']
        self.AUTH0_AUDIENCE = required_vars['AUTH0_AUDIENCE']

    def generate_token(self, user_id: str) -> str:
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=2)
        }
        return jwt.encode(payload, self.SECRET_KEY, algorithm='HS256')

    def verify_token(self, token: str) -> Optional[str]:
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=['HS256'])
            return payload['user_id']
        except jwt.ExpiredSignatureError:
            st.error('Session expired. Please log in again.')
        except jwt.InvalidTokenError as e:
            st.error(f"Invalid session: {str(e)}")
        except Exception as e:
            st.error(f"Token verification failed: {str(e)}")

    def verify_password(self, email: str, password: str) -> bool:
        try:
            print(f"Debug: Trying to verify password for {email}")
            if not hasattr(self.dbs, 'verify_user_password'):
                st.error('Database service configuration error!')
                print(f"Available methods: {dir(self.dbs)}")
                return False
            return self.dbs.verify_user_password(email, password)
        except Exception as e:
            st.error(f"Login failed: {str(e)}")
            print(f"Error details: {repr(e)}")
            return False

    def show_auth(self):
        if st.query_params.get('code'):
            self._handle_oauth_callback()
            return

        st.title('Fitness App Login')
        tab1, tab2 = st.tabs(['Email Login/Register', 'Continue with Google'])

        with tab1:
            self._show_email_auth()

        with tab2:
            st.write("Debug: OAuth Tab Loaded")  # Debug line
            if st.button('Continue with Google', key='google_btn'):
                print("🟢 Google button clicked")  # Debug log
                self._initiate_oauth_flow()

    def _show_email_auth(self):
        auth_type = st.radio('Action:', ['Login', 'Register'], horizontal=True)
        with st.form('auth_form'):
            email = st.text_input('Gmail Address', placeholder='your@gmail.com')
            password = st.text_input('Password', type='password')
            
            if auth_type == 'Register':
                full_name = st.text_input('Full Name')
                confirm_pass = st.text_input('Confirm Password', type='password')
            
            if st.form_submit_button('Login' if auth_type == 'Login' else 'Register'):
                if not email.endswith('@gmail.com'):
                    st.error('Only Gmail accounts (@gmail.com) are allowed')
                    return
                self._handle_email_auth_submit(
                    auth_type, email, password,
                    full_name if auth_type == 'Register' else None,
                    confirm_pass if auth_type == 'Register' else None
                )

    def _initiate_oauth_flow(self):
        st.session_state.oauth_state = str(uuid.uuid4())
        auth_url = (
            f"https://{self.AUTH0_DOMAIN}/authorize?"
            f"response_type=code&"
            f"client_id={self.AUTH0_CLIENT_ID}&"
            f"redirect_uri={REDIRECT_URI}&"
            f"scope=openid%20profile%20email&"
            f"state={st.session_state.oauth_state}&"
            f"audience={self.AUTH0_AUDIENCE}&"
            f"connection=google-oauth2"
        )
        print("\n=== Initiating OAuth Flow ===")
        print(f"State: {st.session_state.oauth_state}")
        print(f"Auth URL: {auth_url}")
        
        # More reliable than JS redirect
        webbrowser.open(auth_url)
        st.info('Please check your browser for Google login')

    def _handle_oauth_callback(self):
        print("🔄 Handling OAuth callback...")
        print("Query params:", dict(st.query_params))  # Debug
        
        code = st.query_params.get("code")
        state = st.query_params.get("state")
        
        if not code:
            st.error("❌ Missing authorization code. Full params: " + str(dict(st.query_params)))
            return
        
        if state != st.session_state.get('oauth_state'):
            st.error("❌ Invalid state parameter")
            print(f"Expected: {st.session_state.get('oauth_state')}, Got: {state}")
            return

        try:
            token = self.oauth_client.fetch_token(
                f"https://{self.AUTH0_DOMAIN}/oauth/token",
                code=code,
                grant_type='authorization_code'
            )
            print("🟢 Token received:", token)  # Debug
            
            userinfo = requests.get(
                f"https://{self.AUTH0_DOMAIN}/userinfo",
                headers={'Authorization': f"Bearer {token['access_token']}"}
            ).json()
            print("🟢 User info:", userinfo)  # Debug
            
            email = userinfo.get('email')
            if not email:
                st.error('No email found in user profile')
                return

            name = userinfo.get('name', email.split('@')[0])
            google_id = userinfo.get('sub')
            user = self.dbs.get_user_by_email(email)

            if not user:
                print('Registering new OAuth user')
                success, result = self.dbs.register_user(
                    email=email,
                    password=None,
                    full_name=name,
                    google_id=google_id
                )
                if not success:
                    st.error(f"Account creation failed: {result}")
                    return
                user = self.dbs.get_user_by_email(email)

            st.session_state.update({
                'authenticated': True,
                'user': {
                    'user_id': user['user_id'],
                    'email': user['email'],
                    'full_name': user.get('full_name', name),
                    'google_id': google_id
                },
                'token': token
            })
            st.query_params.clear()
            st.rerun()

        except Exception as e:
            st.error(f"❌ Authentication failed: {str(e)}")
            print(f"🔴 OAuth callback error: {repr(e)}")

    def _handle_email_auth_submit(self, auth_type: str, email: str, password: str, 
                                full_name: Optional[str] = None, 
                                confirm_password: Optional[str] = None):
        if not email or not password:
            st.error('Email and password are required')
            return

        if auth_type == 'Register':
            if not full_name:
                st.error('Full name is required')
                return
            if password != confirm_password:
                st.error('Passwords do not match')
                return
            if len(password) < 8:
                st.error('Password must be at least 8 characters')
                return
            
            success, result = self.dbs.register_user(
                email=email,
                password=password,
                full_name=full_name
            )
            if not success:
                st.error(result)
                return
            st.success('Account created successfully! Please log in.')
        else:
            if not self.verify_password(email, password):
                st.error('Invalid email or password')
                return
            
            user = self.dbs.get_user_by_email(email)
            if not user:
                st.error('User not found')
                return
            
            st.session_state.update({
                'authenticated': True,
                'user': {
                    'user_id': user['user_id'],
                    'email': user['email'],
                    'full_name': user.get('full_name', 'User')
                }
            })
            st.rerun()

    def logout(self):
        keys_to_clear = ['authenticated', 'user', 'oauth_state', 'auth_error', 'token']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.success('You have been successfully logged out.')
        st.experimental_set_query_params()
        st.rerun()

# Singleton instance
auth_service = AuthService()
show_auth = auth_service.show_auth
logout = auth_service.logout
generate_token = auth_service.generate_token
verify_token = auth_service.verify_token
verify_password = auth_service.verify_password