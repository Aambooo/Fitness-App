import uuid
import requests
from requests.exceptions import RequestException
import streamlit as st
from streamlit.components.v1 import html  # Correct import
import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import database_service as dbs
from typing import Optional, Dict, Any
import webbrowser
from authlib.integrations.requests_client import OAuth2Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import time

load_dotenv()

# Separate the redirect URIs for Google and Auth0
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8501/auth/callback')
AUTH0_CALLBACK_URL = os.getenv('AUTH0_CALLBACK_URL', 'http://localhost:8501/auth/callback')


class AuthService:
    def __init__(self, dbs_service=None):
        self.dbs = dbs_service
        self.validate_auth_config()
        self.oauth_client = OAuth2Session(
            client_id=self.AUTH0_CLIENT_ID,
            client_secret=self.AUTH0_CLIENT_SECRET,
            redirect_uri=AUTH0_CALLBACK_URL,
            scope='openid profile email'
        )
    def validate_auth_config(self):
        required_vars = {
            'AUTH0_CLIENT_ID': os.getenv('AUTH0_CLIENT_ID'),
            'AUTH0_CLIENT_SECRET': os.getenv('AUTH0_CLIENT_SECRET'),
            'AUTH0_DOMAIN': os.getenv('AUTH0_DOMAIN'),
            'SECRET_KEY': os.getenv('SECRET_KEY'),
            'AUTH0_AUDIENCE': os.getenv('AUTH0_AUDIENCE'),
            'GOOGLE_CLIENT_ID': os.getenv('GOOGLE_CLIENT_ID'),
            'GOOGLE_CLIENT_SECRET': os.getenv('GOOGLE_CLIENT_SECRET')
        }
        missing_vars = [k for (k, v) in required_vars.items() if not v]
        if missing_vars:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        self.AUTH0_CLIENT_ID = required_vars['AUTH0_CLIENT_ID']
        self.AUTH0_CLIENT_SECRET = required_vars['AUTH0_CLIENT_SECRET']
        self.AUTH0_DOMAIN = required_vars['AUTH0_DOMAIN']
        self.SECRET_KEY = required_vars['SECRET_KEY']
        self.AUTH0_AUDIENCE = required_vars['AUTH0_AUDIENCE']
        self.GOOGLE_CLIENT_ID = required_vars['GOOGLE_CLIENT_ID']
        self.GOOGLE_CLIENT_SECRET = required_vars['GOOGLE_CLIENT_SECRET']

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
            return self.dbs.verify_user_password(email, password)
        except Exception as e:
            st.error(f"Login failed: {str(e)}")
            return False
    
    def show_auth(self):
        """Main authentication interface"""
        if 'oauth_state' in st.session_state:
            del st.session_state['oauth_state']

        if st.query_params.get('code'):
            self._handle_auth_callback()
            return
            
        st.title('Your Fitness Reminder')
        tab1, tab2 = st.tabs(['Email Login/Register', 'Continue with Google'])
        
        with tab1:
            self._show_email_auth()
        
        with tab2:
            self._show_google_auth()

    def _show_google_auth(self):
        """Google Sign-In button with state parameter"""
        state = str(uuid.uuid4())
        st.session_state['oauth_state'] = state
        
        google_oauth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={self.GOOGLE_CLIENT_ID}&"
            f"redirect_uri={GOOGLE_REDIRECT_URI}&"
            f"response_type=code&"
            f"scope=openid%20email%20profile&"
            f"state={state}&"
            f"access_type=offline&"
            f"prompt=select_account"
        )
        
        st.markdown(f"""
            <a href="{google_oauth_url}" target="_blank">
                <button style="
                    background: #4285F4;
                    color: white;
                    border: none;
                    padding: 10px 24px;
                    border-radius: 4px;
                    font-size: 16px;
                    cursor: pointer;
                    margin-top: 10px;
                ">
                    <img src="https://fonts.gstatic.com/s/i/productlogos/googleg/v6/24px.svg" 
                         style="vertical-align: middle; margin-right: 8px;">
                    Sign in with Google
                </button>
            </a>
        """, unsafe_allow_html=True)
        st.caption("You'll be redirected to Google in a new tab")

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
                    auth_type,
                    email,
                    password,
                    full_name if auth_type == 'Register' else None,
                    confirm_pass if auth_type == 'Register' else None
                )

    def _show_google_auth(self):
        # First ensure we're not in a callback state
        if 'code' not in st.query_params and 'state' not in st.query_params:
            # Generate a unique state token
            state = str(uuid.uuid4())
            st.session_state['oauth_state'] = state
    
            # Build the authorization URL
            auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth?"
                f"client_id={self.GOOGLE_CLIENT_ID}&"
                f"redirect_uri={GOOGLE_REDIRECT_URI}&"
                "response_type=code&"
                "scope=openid%20email%20profile&"
                f"state={state}&"
                "access_type=offline&"
                "prompt=select_account"
            )
        
            # Simple and reliable Streamlit button
            with st.container():
                st.markdown("### Continue with Google")
                st.link_button(
                    label="Continue with Google",
                    url=auth_url,
                    type="secondary",
                    use_container_width=True
                )

    def _handle_auth_callback(self):
        """Handles Google OAuth callback"""
        st.write("## 🕵️‍♂️ OAuth Debug")
        st.write("Current session state:", st.session_state.get('oauth_state'))
        st.write("Received URL state:", st.query_params.get('state'))
        st.write("All URL parameters:", dict(st.query_params))

        # State validation
        if 'state' not in st.query_params:
            st.error("❌ Missing state parameter - possible security issue")
            st.stop()
        
        if st.query_params['state'] != st.session_state.get('oauth_state'):
            st.error("❌ State mismatch - possible CSRF attack")
            st.stop()

        # Token exchange
        if 'code' not in st.query_params:
            st.error("⚠️ Missing authorization code")
            st.stop()

        try:
            # Exchange code for tokens
            oauth = OAuth2Session(
                client_id=self.GOOGLE_CLIENT_ID,
                client_secret=self.GOOGLE_CLIENT_SECRET,
                redirect_uri=GOOGLE_REDIRECT_URI,
                scope=['openid', 'email', 'profile']
            )
            
            token = oauth.fetch_token(
                url="https://oauth2.googleapis.com/token",
                code=st.query_params['code'],
                authorization_response=dict(st.query_params)
            )

            # Verify ID token
            idinfo = id_token.verify_oauth2_token(
                token['id_token'],
                google_requests.Request(),
                self.GOOGLE_CLIENT_ID
            )

            # Handle user registration/login
            email = idinfo['email']
            name = idinfo.get('name', email.split('@')[0])
            google_id = idinfo['sub']

            user = self.dbs.get_user_by_email(email)
        
            if not user:
                success, result = self.dbs.register_user(
                    email=email,
                    password=None,
                    full_name=name,
                    google_id=google_id
                )
            
                if not success:
                    st.error(f"❌ Registration failed: {result}")
                    st.stop()
            
                user = self.dbs.get_user_by_email(email)

            # Update session
            st.session_state.update({
                'authenticated': True,
                'user': {
                    'user_id': user['user_id'],
                    'email': user['email'],
                    'full_name': user.get('full_name', name),
                    'google_token': token['access_token']
                }
            })

            # Cleanup and redirect
            if 'oauth_state' in st.session_state:
                del st.session_state['oauth_state']
            
            st.experimental_set_query_params()
            st.success("🎉 Authentication Successful! Redirecting...")
            time.sleep(1.5)
            st.rerun()

        except Exception as e:
            st.error(f"❌ Authentication Failed: {str(e)}")
            st.stop()

    def _handle_google_callback(self):
        st.write("Google callback received!")  # Temporary debug
        st.write(st.query_params)
        try:
            token = st.query_params['google_token']
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                self.GOOGLE_CLIENT_ID
            )
            
            email = idinfo['email']
            name = idinfo.get('name', email.split('@')[0])
            google_id = idinfo['sub']
            
            user = self.dbs.get_user_by_email(email)
            if not user:
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
                }
            })
            st.query_params.clear()
            st.rerun()
            
        except ValueError as e:
            st.error(f"Google login failed: {str(e)}")
            st.stop()

    def _handle_auth0_callback(self):
        code = st.query_params.get('code')
        state = st.query_params.get('state')
        
        if not code:
            st.error('❌ Missing authorization code')
            return
            
        if state != st.session_state.get('oauth_state'):
            st.error('❌ Invalid state parameter')
            return
            
        try:
            token = self.oauth_client.fetch_token(
                f"https://{self.AUTH0_DOMAIN}/oauth/token",
                code=code,
                grant_type='authorization_code'
            )
            
            userinfo = requests.get(
                f"https://{self.AUTH0_DOMAIN}/userinfo",
                headers={'Authorization': f"Bearer {token['access_token']}"}
            ).json()
            
            email = userinfo.get('email')
            if not email:
                st.error('No email found in user profile')
                return
                
            name = userinfo.get('name', email.split('@')[0])
            google_id = userinfo.get('sub')
            
            user = self.dbs.get_user_by_email(email)
            if not user:
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
            st.stop()

    def _handle_email_auth_submit(self, auth_type: str, email: str, password: str,
                                full_name: Optional[str] = None, confirm_password: Optional[str] = None):
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

    def logout(self):  # <- Method is now properly defined
        """Clear all authentication-related session state"""
        keys_to_remove = [
            'authenticated',
            'user',
            'oauth_state',
            'token',
            'auth_error'
        ]
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
        st.query_params.clear()
        st.success("You have been successfully logged out!")
        st.rerun()
if not hasattr(AuthService, 'logout'):
    raise NotImplementedError("AuthService must implement logout() method")

# Initialize the auth service
auth_service = AuthService(dbs_service=None)

show_auth = auth_service.show_auth
logout = auth_service.logout
generate_token = auth_service.generate_token
verify_token = auth_service.verify_token
verify_password = auth_service.verify_password