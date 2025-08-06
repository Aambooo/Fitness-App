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
        """Nuclear password verification"""
        try:
            print(f"\n🔐 NUCLEAR VERIFICATION FOR {email}")
            user = self.dbs.get_user_by_email(email)
            if not user:
                print("❌ USER NOT FOUND")
                return False

            stored_hash = user["password_hash"]
            print(f"STORED HASH: {stored_hash[:60]}...")

            # Direct bcrypt comparison
            is_valid = bcrypt.checkpw(
                password.encode("utf-8"), stored_hash.encode("utf-8")
            )
            print(f"PASSWORD MATCHES: {is_valid}")

            # Emergency fallback check
            if not is_valid:
                print("⚠️ EMERGENCY COMPARISON:")
                print(f"Input: {password[:2]}...")
                print(f"Stored: {stored_hash[:60]}...")

            return is_valid

        except Exception as e:
            print(f"💥 VERIFICATION CRASHED: {str(e)}")
            return False

    def is_recent_password(self, email: str, new_password: str) -> bool:
        """Check if password matches any of the last 3 used passwords"""
        user = self.dbs.get_user_by_email(email)
        if not user:
            return False

        # Get previous hashes (ensure your DB stores these)
        previous_hashes = user.get("previous_hashes", [])
        if not isinstance(
            previous_hashes, list
        ):  # Handle cases where it's None or malformed
            previous_hashes = []

        # Check against last 3 hashes
        for old_hash in previous_hashes[:3]:
            if bcrypt.checkpw(new_password.encode("utf-8"), old_hash.encode("utf-8")):
                return True
        return False

    def send_verification_email(self, email: str) -> bool:
        """Send email with verification link"""
        token = self.generate_token(email)
        verification_link = (
            f"http://localhost:8501/verify?token={token}"  # Add `/verify` path
        )

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
                login_submitted = st.form_submit_button("Login")

                if login_submitted:
                    self._handle_login(email, password)

        with tab2:
            with st.form("register_form"):
                st.warning(
                    "Note: We'll send a verification link. If you don't own this email, "
                    "you won't be able to complete registration."
                )
                email = st.text_input("Email", placeholder="your@gmail.com")
                full_name = st.text_input("Full Name")
                password = st.text_input("Password", type="password")
                confirm_pass = st.text_input("Confirm Password", type="password")

                if st.form_submit_button("Register"):
                    self._handle_register(email, full_name, password, confirm_pass)

    def _handle_login(self, email: str, password: str):
        user = self.dbs.get_user_by_email(email)

        if not user:
            st.error("❌ Account not found")
            return

        if not user.get("is_verified"):
            st.error("⚠️ Please verify your email first. Check your inbox.")
            return

        if not self.verify_password(email, password):
            st.error("❌ Invalid credentials")
            return

        # Successful login
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
        """Handle user registration with email verification flow

        Args:
            email: User's email address
            full_name: User's full name
            password: User's password
            confirm_pass: Password confirmation
        """
        # 1. Validate email format (strict Gmail check)
        if not self._validate_gmail_format(email):
            st.error("❌ Only @gmail.com addresses are allowed")
            return

        # 2. Verify Gmail existence via SMTP
        try:
            if not self._verify_gmail_exists(email):
                st.error("❌ This Gmail doesn't exist. Use a valid Google account.")
                return
        except Exception as e:
            st.error(f"❌ Email verification failed: {str(e)}")
            return

        # 3. Check if email is already registered (including unverified accounts)
        existing_user = self.dbs.get_user_by_email(email)
        if existing_user:
            if existing_user.get("is_verified"):
                st.error("❌ Email already registered")
            else:
                st.warning(
                    "⚠️ This email has an unverified account. Resending verification..."
                )
                self.send_verification_email(email)
                st.success("✅ New verification email sent! Check your inbox.")
            return

        # 4. Validate password requirements
        if len(password) < 8:
            st.error("❌ Password must be at least 8 characters")
            return
        if password != confirm_pass:
            st.error("❌ Passwords don't match")
            return

        # 5. Register new unverified user
        success, message = self.dbs.register_user(
            email=email, password=password, full_name=full_name
        )

        if success:
            # Send verification email
            if self.send_verification_email(email):
                st.success("✅ Verification email sent! Check your inbox.")
                # Optional: Show the verification reminder
                with st.expander("Didn't receive the email?"):
                    st.markdown(
                        """
                    - Check your spam folder
                    - Wait 2-3 minutes
                    - [Click here to resend](#) (implement resend logic)
                    """
                    )
            else:
                # Rollback registration if email fails
                self.dbs.delete_user(email)
                st.error("❌ Failed to send verification email")
        else:
            st.error(f"❌ {message}")

    def _validate_gmail_format(self, email: str) -> bool:
        """More robust email validation"""
        if not email or not isinstance(email, str):
            return False
        try:
            pattern = r"^[a-zA-Z0-9._%+-]+@gmail\.com$"
            return bool(
                re.match(pattern, email.lower())
            )  # Add .lower() for consistency
        except AttributeError:
            return False

    def _verify_gmail_exists(self, email: str) -> bool:
        """Check if Gmail exists by attempting to send a test email."""
        try:
            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()
                server.login(self.SMTP_USER, self.SMTP_PASS)

                # Try sending a test email (empty)
                server.sendmail(
                    from_addr=self.SMTP_USER,
                    to_addrs=email,
                    msg="Subject: Test\n\n",  # Minimal email
                )
            return True
        except smtplib.SMTPRecipientsRefused:
            return False  # Email doesn't exist
        except Exception as e:
            st.error(f"❌ SMTP error: {str(e)}")
            return False  # Fail safely

    def verify_email_token(self, token: str) -> bool:
        email = self.verify_token(token)
        if not email:
            return False

        return self.dbs.mark_user_as_verified(email)

    def logout(self):
        st.session_state.pop("authenticated", None)
        st.session_state.pop("user", None)
        st.rerun()


# Singleton instance for easy imports
auth_service = AuthService(dbs_service=None)
show_auth = auth_service.show_auth
logout = auth_service.logout
generate_token = auth_service.generate_token
verify_token = auth_service.verify_token
verify_password = auth_service.verify_password
