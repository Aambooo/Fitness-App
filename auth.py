
import streamlit as st
from auth0_component import login_button
import os
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import database_service as dbs

load_dotenv()

# Auth0 configuration
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")

def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=2)
    }
    return jwt.encode(payload, os.getenv("SECRET_KEY"), algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=['HS256'])
        return payload['user_id']
    except:
        return None

def google_auth():
    user_info = login_button(
        client_id=AUTH0_CLIENT_ID,
        domain=AUTH0_DOMAIN,
        key="google"
    )
    if user_info:
        email = user_info['email']
        name = user_info['name']
        google_id = user_info['sub']
        
        # Check if user exists
        try:
            user = dbs.get_user_by_email(email)
        except:
            # Register new user
            dbs.register_user(email, None, name, google_id)
            user = dbs.get_user_by_email(email)
        
        token = generate_token(user['user_id'])
        st.session_state['token'] = token
        st.session_state['user'] = user
        st.experimental_rerun()

def email_auth():
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            try:
                user = dbs.get_user_by_email(email)
                if user and user['password'] == password:  # In production, use hashed passwords!
                    token = generate_token(user['user_id'])
                    st.session_state['token'] = token
                    st.session_state['user'] = user
                    st.experimental_rerun()
                else:
                    st.error("Invalid credentials")
            except:
                st.error("User not found")

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
                except:
                    st.error("Email already registered")
            else:
                st.error("Passwords don't match")

def logout():
    st.session_state.pop('token', None)
    st.session_state.pop('user', None)
    st.experimental_rerun()

def show_auth():
    st.title("Welcome to Fitness App")
    
    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Continue with Google"])
    
    with tab1:
        email_auth()
    
    with tab2:
        register_form()
    
    with tab3:
        google_auth()