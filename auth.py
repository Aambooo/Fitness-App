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
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501/")
AUTH0_CALLBACK_URL = os.getenv(
    "AUTH0_CALLBACK_URL", "http://localhost:8501/auth/callback"
)


class AuthService:
    def __init__(self, dbs_service=None):
        self.dbs = dbs_service
        self.validate_auth_config()
        self.oauth_client = OAuth2Session(
            client_id=self.AUTH0_CLIENT_ID,
            client_secret=self.AUTH0_CLIENT_SECRET,
            redirect_uri=AUTH0_CALLBACK_URL,
            scope="openid profile email",
        )

    def validate_auth_config(self):
        required_vars = {
            "AUTH0_CLIENT_ID": os.getenv("AUTH0_CLIENT_ID"),
            "AUTH0_CLIENT_SECRET": os.getenv("AUTH0_CLIENT_SECRET"),
            "AUTH0_DOMAIN": os.getenv("AUTH0_DOMAIN"),
            "SECRET_KEY": os.getenv("SECRET_KEY"),
            "AUTH0_AUDIENCE": os.getenv("AUTH0_AUDIENCE"),
            "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID"),
            "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET"),
        }
        missing_vars = [k for (k, v) in required_vars.items() if not v]
        if missing_vars:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        self.AUTH0_CLIENT_ID = required_vars["AUTH0_CLIENT_ID"]
        self.AUTH0_CLIENT_SECRET = required_vars["AUTH0_CLIENT_SECRET"]
        self.AUTH0_DOMAIN = required_vars["AUTH0_DOMAIN"]
        self.SECRET_KEY = required_vars["SECRET_KEY"]
        self.AUTH0_AUDIENCE = required_vars["AUTH0_AUDIENCE"]
        self.GOOGLE_CLIENT_ID = required_vars["GOOGLE_CLIENT_ID"]
        self.GOOGLE_CLIENT_SECRET = required_vars["GOOGLE_CLIENT_SECRET"]

    def generate_token(self, user_id: str) -> str:
        payload = {"user_id": user_id, "exp": datetime.utcnow() + timedelta(hours=2)}
        return jwt.encode(payload, self.SECRET_KEY, algorithm="HS256")

    def verify_token(self, token: str) -> Optional[str]:
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=["HS256"])
            return payload["user_id"]
        except jwt.ExpiredSignatureError:
            st.error("Session expired. Please log in again.")
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
        if "oauth_state" in st.session_state:
            del st.session_state["oauth_state"]

        if st.query_params.get("code"):
            self._handle_auth_callback()
            return

        st.title("Your Fitness Reminder")
        tab1, tab2 = st.tabs(["Email Login/Register", "Continue with Google"])

        with tab1:
            self._show_email_auth()

        with tab2:
            self._show_google_auth()

    def _show_email_auth(self):
        auth_type = st.radio("Action:", ["Login", "Register"], horizontal=True)
        with st.form("auth_form"):
            email = st.text_input("Gmail Address", placeholder="your@gmail.com")
            password = st.text_input("Password", type="password")

            if auth_type == "Register":
                full_name = st.text_input("Full Name")
                confirm_pass = st.text_input("Confirm Password", type="password")

            if st.form_submit_button("Login" if auth_type == "Login" else "Register"):
                if not email.endswith("@gmail.com"):
                    st.error("Only Gmail accounts (@gmail.com) are allowed")
                    return

                self._handle_email_auth_submit(
                    auth_type,
                    email,
                    password,
                    full_name if auth_type == "Register" else None,
                    confirm_pass if auth_type == "Register" else None,
                )

    def _show_google_auth(self):
        """Initialize Google OAuth flow with debug verification"""
        # ================================================
        # 1. ENVIRONMENT VERIFICATION (Add this FIRST)
        # ================================================
        print(f"\n=== OAuth Environment Verification ===")
        print(f"GOOGLE_REDIRECT_URI: {GOOGLE_REDIRECT_URI}")
        print(
            f"GOOGLE_CLIENT_ID: {self.GOOGLE_CLIENT_ID[:10]}..."
        )  # First 10 chars for security

        if not all(
            [GOOGLE_REDIRECT_URI, self.GOOGLE_CLIENT_ID, self.GOOGLE_CLIENT_SECRET]
        ):
            raise ValueError("Missing required Google OAuth environment variables")

        if "code" not in st.query_params:
            state = str(uuid.uuid4())

            # Store state in multiple reliable locations
            st.session_state["oauth_state"] = state  # Primary storage

            # Alternative storage methods
            js = f"""
            <script>
                // Store in both storage locations
                localStorage.setItem('oauth_state', '{state}');
                sessionStorage.setItem('oauth_state', '{state}');
            
                // Ensure full URL encoding
                let authUrl = `https://accounts.google.com/o/oauth2/v2/auth?${{
                    new URLSearchParams({{
                        client_id: '{self.GOOGLE_CLIENT_ID}',
                        redirect_uri: '{GOOGLE_REDIRECT_URI}',
                        response_type: 'code',
                        scope: 'openid email profile',
                        state: '{state}',
                        access_type: 'offline',
                        prompt: 'select_account'
                    }}).toString()
                }}`;
            
                // Force top-level navigation
                window.top.location.href = authUrl;
            </script>
            """
            st.components.v1.html(js, height=0)

            auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={self.GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&response_type=code&scope=openid%20email%20profile&state={state}&access_type=offline&prompt=select_account"

            # Create a visible button with secure redirect
            button_html = f"""
            <div style="margin: 1rem 0;">
                <a href="{auth_url}" onclick="
                    window.open('{auth_url}', '_top');
                    return false;
                " style="text-decoration: none;">
                    <div style="
                        background: #4285F4;
                        color: white;
                        border-radius: 4px;
                        padding: 10px 16px;
                        font-family: 'Roboto', sans-serif;
                        font-size: 14px;
                        font-weight: 500;
                        display: inline-flex;
                        align-items: center;
                        cursor: pointer;
                    ">
                        <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" 
                         style="width: 18px; margin-right: 8px;">
                        Continue with Google
                    </div>
                </a>
                <p style="font-size: 0.8rem; color: #666; margin-top: 0.5rem;">
                You'll be redirected to Google's secure login page
                </p>
            </div>
            """
            st.markdown(button_html, unsafe_allow_html=True)

    def _handle_auth_callback(self):
        """Callback handler with comprehensive state recovery"""

        print(f"\n=== DEBUG: Received OAuth Params ===")
        print(f"Full URL Params: {dict(st.query_params)}")
        print(f"Session State: {st.session_state.get('oauth_state')}")

        url_state = st.query_params.get("state")

        if not url_state:
            st.error("Missing state parameter in callback")
            st.stop()

        # Check all possible state sources
        valid_state = None
        state_sources = {
            "Session State": st.session_state.get("oauth_state"),
            "Browser Storage": None,  # Will be filled by JavaScript
        }

        # Retrieve browser storage values
        js_check = f"""
        <script>
            const storedState = localStorage.getItem('google_oauth_state') || 
                          sessionStorage.getItem('google_oauth_state');
            window.parent.postMessage({{
                type: 'oauth_state_report',
                state: storedState,
                url_state: '{url_state}'
            }}, '*');
        </script>
        """
        st.components.v1.html(js_check, height=0)

        # Simple timeout for JS execution
        time.sleep(0.5)

        if st.session_state.get("oauth_state") == url_state:
            valid_state = url_state

        if not valid_state:
            st.error(
                f"""
            ❌ State Mismatch Detected
            Expected: {st.session_state.get('oauth_state')}
            Received: {url_state}
            """
            )

            if st.button("🔄 Restart Authentication"):
                keys = ["oauth_state", "auth_error"]
                for key in keys:
                    st.session_state.pop(key, None)
                st.query_params.clear()
                st.rerun()
                st.stop()
            # Token exchange
        try:
            oauth = OAuth2Session(
                client_id=self.GOOGLE_CLIENT_ID,
                client_secret=self.GOOGLE_CLIENT_SECRET,
                redirect_uri=GOOGLE_REDIRECT_URI,
                scope=["openid", "email", "profile"],
            )

            token = oauth.fetch_token(
                url="https://oauth2.googleapis.com/token",
                code=st.query_params["code"],
                authorization_response=dict(st.query_params),
            )

            idinfo = id_token.verify_oauth2_token(
                token["id_token"], google_requests.Request(), self.GOOGLE_CLIENT_ID
            )

            # User management
            email = idinfo["email"]
            name = idinfo.get("name", email.split("@")[0])
            google_id = idinfo["sub"]

            user = self.dbs.get_user_by_email(email)
            if not user:
                success, result = self.dbs.register_user(
                    email=email, password=None, full_name=name, google_id=google_id
                )
                if not success:
                    st.error(f"Registration failed: {result}")
                    st.stop()
                user = self.dbs.get_user_by_email(email)

            # Update session
            st.session_state.update(
                {
                    "authenticated": True,
                    "user": {
                        "user_id": user["user_id"],
                        "email": user["email"],
                        "full_name": user.get("full_name", name),
                        "google_token": token["access_token"],
                    },
                }
            )

            # Cleanup
            keys_to_remove = ["oauth_state", "auth_error"]
            for key in keys_to_remove:
                if key in st.session_state:
                    del st.session_state[key]

            # Modern query params clearing
            st.query_params.clear()

            st.success("🎉 Authentication Successful!")
            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            st.stop()

    def _handle_google_callback(self):
        st.write("Google callback received!")  # Temporary debug
        st.write(st.query_params)
        try:
            token = st.query_params["google_token"]
            idinfo = id_token.verify_oauth2_token(
                token, google_requests.Request(), self.GOOGLE_CLIENT_ID
            )

            email = idinfo["email"]
            name = idinfo.get("name", email.split("@")[0])
            google_id = idinfo["sub"]

            user = self.dbs.get_user_by_email(email)
            if not user:
                success, result = self.dbs.register_user(
                    email=email, password=None, full_name=name, google_id=google_id
                )
                if not success:
                    st.error(f"Account creation failed: {result}")
                    return
                user = self.dbs.get_user_by_email(email)

            st.session_state.update(
                {
                    "authenticated": True,
                    "user": {
                        "user_id": user["user_id"],
                        "email": user["email"],
                        "full_name": user.get("full_name", name),
                        "google_id": google_id,
                    },
                }
            )
            st.query_params.clear()
            st.rerun()

        except ValueError as e:
            st.error(f"Google login failed: {str(e)}")
            st.stop()

    def _handle_auth0_callback(self):
        code = st.query_params.get("code")
        state = st.query_params.get("state")

        if not code:
            st.error("❌ Missing authorization code")
            return

        if state != st.session_state.get("oauth_state"):
            st.error("❌ Invalid state parameter")
            return

        try:
            token = self.oauth_client.fetch_token(
                f"https://{self.AUTH0_DOMAIN}/oauth/token",
                code=code,
                grant_type="authorization_code",
            )

            userinfo = requests.get(
                f"https://{self.AUTH0_DOMAIN}/userinfo",
                headers={"Authorization": f"Bearer {token['access_token']}"},
            ).json()

            email = userinfo.get("email")
            if not email:
                st.error("No email found in user profile")
                return

            name = userinfo.get("name", email.split("@")[0])
            google_id = userinfo.get("sub")

            user = self.dbs.get_user_by_email(email)
            if not user:
                success, result = self.dbs.register_user(
                    email=email, password=None, full_name=name, google_id=google_id
                )
                if not success:
                    st.error(f"Account creation failed: {result}")
                    return
                user = self.dbs.get_user_by_email(email)

            st.session_state.update(
                {
                    "authenticated": True,
                    "user": {
                        "user_id": user["user_id"],
                        "email": user["email"],
                        "full_name": user.get("full_name", name),
                        "google_id": google_id,
                    },
                    "token": token,
                }
            )
            st.query_params.clear()
            st.rerun()

        except Exception as e:
            st.error(f"❌ Authentication failed: {str(e)}")
            st.stop()

    def _handle_email_auth_submit(
        self,
        auth_type: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        confirm_password: Optional[str] = None,
    ):
        if not email or not password:
            st.error("Email and password are required")
            return

        if auth_type == "Register":
            if not full_name:
                st.error("Full name is required")
                return

            if password != confirm_password:
                st.error("Passwords do not match")
                return

            if len(password) < 8:
                st.error("Password must be at least 8 characters")
                return

            success, result = self.dbs.register_user(
                email=email, password=password, full_name=full_name
            )

            if not success:
                st.error(result)
                return

            st.success("Account created successfully! Please log in.")
        else:
            if not self.verify_password(email, password):
                st.error("Invalid email or password")
                return

            user = self.dbs.get_user_by_email(email)
            if not user:
                st.error("User not found")
                return

            st.session_state.update(
                {
                    "authenticated": True,
                    "user": {
                        "user_id": user["user_id"],
                        "email": user["email"],
                        "full_name": user.get("full_name", "User"),
                    },
                }
            )
            st.rerun()

    def logout(self):  # <- Method is now properly defined
        """Clear all authentication-related session state"""
        keys_to_remove = ["authenticated", "user", "oauth_state", "token", "auth_error"]
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
        st.query_params.clear()
        st.success("You have been successfully logged out!")
        st.rerun()


if not hasattr(AuthService, "logout"):
    raise NotImplementedError("AuthService must implement logout() method")

# Initialize the auth service
auth_service = AuthService(dbs_service=None)

show_auth = auth_service.show_auth
logout = auth_service.logout
generate_token = auth_service.generate_token
verify_token = auth_service.verify_token
verify_password = auth_service.verify_password
