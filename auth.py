import streamlit as st
import os, jwt, bcrypt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import database_service as dbs
from typing import Optional
import re
import smtplib
from email.mime.text import MIMEText

load_dotenv()


class AuthService:
    def __init__(self, dbs_service=None):
        self.dbs = dbs_service
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        self.SMTP_USER = os.getenv("SMTP_USER")
        self.SMTP_PASS = os.getenv("SMTP_PASS")
        self.SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

        if not all([self.SECRET_KEY, self.SMTP_USER, self.SMTP_PASS]):
            raise RuntimeError("Missing required environment variables")

    def generate_token(self, email: str) -> str:
        payload = {"email": email, "exp": datetime.utcnow() + timedelta(hours=2)}
        return jwt.encode(payload, self.SECRET_KEY, algorithm="HS256")

    def verify_token(self, token: str) -> Optional[str]:
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=["HS256"])
            return payload["email"]
        except jwt.ExpiredSignatureError:
            st.error("Verification link expired")
        except jwt.InvalidTokenError:
            st.error("Invalid verification link")
        except Exception as e:
            st.error(f"Error: {str(e)}")

    def verify_password(self, email: str, password: str) -> bool:
        try:
            return self.dbs.verify_user_password(email, password)
        except Exception as e:
            st.error(f"Login failed: {str(e)}")
            return False

    def send_verification_email(self, email: str) -> bool:
        """Send email with verification link"""
        token = self.generate_token(email)
        verification_link = f"http://localhost:8501/?token={token}"

        message = f"""
        <html>
            <body>
                <p>Please verify your email by clicking:</p>
                <a href="{verification_link}">Verify Email</a>
                <p>This link expires in 2 hours.</p>
            </body>
        </html>
        """

        try:
            msg = MIMEText(message, "html")
            msg["Subject"] = "Verify Your Email"
            msg["From"] = self.SMTP_USER
            msg["To"] = email

            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()
                server.login(self.SMTP_USER, self.SMTP_PASS)
                server.send_message(msg)
            return True
        except Exception as e:
            st.error(f"Failed to send email: {str(e)}")
            return False

    def show_auth(self):
        st.title("Fitness Reminder")
        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="your@gmail.com")
                password = st.text_input("Password", type="password")

                if st.form_submit_button("Login"):
                    self._handle_login(email, password)

        with tab2:
            with st.form("register_form"):
                email = st.text_input("Email", placeholder="your@gmail.com")
                full_name = st.text_input("Full Name")
                password = st.text_input("Password", type="password")
                confirm_pass = st.text_input("Confirm Password", type="password")

                if st.form_submit_button("Register"):
                    self._handle_register(email, full_name, password, confirm_pass)

    def _handle_login(self, email: str, password: str):
        if not self._validate_gmail(email):
            return

        if not self.verify_password(email, password):
            return

        user = self.dbs.get_user_by_email(email)
        if not user:
            st.error("User not found")
            return

        if not user.get("is_verified", False):
            st.error("Please verify your email first")
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

    def _handle_register(
        self, email: str, full_name: str, password: str, confirm_pass: str
    ):
        if not self._validate_gmail(email):
            return

        if not full_name:
            st.error("Full name required")
            return

        if len(password) < 8:
            st.error("Password must be 8+ characters")
            return

        if password != confirm_pass:
            st.error("Passwords don't match")
            return

        success, message = self.dbs.register_user(
            email=email, password=password, full_name=full_name, is_verified=False
        )

        if not success:
            st.error(message)
            return

        if self.send_verification_email(email):
            st.success("Verification email sent! Check your inbox.")
        else:
            st.error("Failed to send verification email")

    def _validate_gmail(self, email: str) -> bool:
        if not re.match(r"^[\w\.-]+@gmail\.com$", email):
            st.error("Only @gmail.com addresses allowed")
            return False
        return True

    def verify_email_token(self, token: str) -> bool:
        email = self.verify_token(token)
        if not email:
            return False

        return self.dbs.mark_user_as_verified(email)

    def logout(self):
        st.session_state.pop("authenticated", None)
        st.session_state.pop("user", None)
        st.rerun()


# Singleton instance
auth_service = AuthService(dbs_service=None)
show_auth = auth_service.show_auth
logout = auth_service.logout
generate_token = auth_service.generate_token
verify_token = auth_service.verify_token
verify_password = auth_service.verify_password
