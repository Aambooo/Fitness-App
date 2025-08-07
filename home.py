import streamlit as st
import base64


# --- BACKGROUND IMAGE ---
def set_bg(image_file):
    with open(image_file, "rb") as image:
        encoded = base64.b64encode(image.read()).decode()
    st.markdown(
        f"""
        <style>
            html {{
                scroll-behavior: smooth;
            }}
            .stApp {{
                background-image: url("data:image/png;base64,{encoded}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
                overflow-x: hidden;
            }}
            .hero-container {{
                background-color: rgba(0, 0, 0, 0.6);
                padding: 120px 40px 80px 40px;
                border-radius: 20px;
                text-align: center;
                margin-top: 60px;
            }}
            .how-it-works-container {{
                background-color: rgba(0, 0, 0, 0.6);
                padding: 80px 40px 60px 40px;
                border-radius: 20px;
                margin-top: 40px;
                margin-bottom: 60px;
            }}
            .hero-title {{
                font-size: 60px;
                color: white;
                font-weight: bold;
                margin-bottom: 20px;
            }}
            .hero-subtitle {{
                font-size: 22px;
                color: #f0f0f0;
                margin-bottom: 40px;
            }}
            .custom-btn {{
                padding: 15px 30px;
                font-size: 18px;
                border-radius: 10px;
                background: white;
                color: black;
                border: none;
                cursor: pointer;
                margin: 10px;
                font-weight: bold;
            }}
            .custom-btn:hover {{
                background: darkred;
            }}
            .card {{
                background-color: white;
                color: black;
                border-radius: 16px;
                padding: 30px 25px;
                width: 280px;
                text-align: center;
                box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            }}
            .card h3 {{
                font-size: 26px;
                margin-bottom: 15px;
            }}
            .card p {{
                font-size: 17px;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# --- HERO SECTION ---
def hero_section():
    set_bg("assets/barbell.jpg")

    st.markdown(
        """
        <div class="hero-container">
            <div class="hero-title">Your Fitness Reminder</div>
            <div class="hero-subtitle">
                Tired of missing your favorite YouTube workouts?<br>
                Let us remind you, so you never skip a sweat session again!
            </div>
            <div style="display: flex; justify-content: center; gap: 20px;">
                <a href="/?login=1">
                    <button class="custom-btn">Login / Register</button>
                </a>
                <a href="#how-it-works">
                    <button class="custom-btn">How It Works</button>
                </a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --- HOW IT WORKS SECTION ---
def how_it_works():
    st.markdown("<div id='how-it-works'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="how-it-works-container">
            <h2 style='text-align:center; color:white; font-size: 40px;'>How It Works</h2>
            <div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 40px; margin-top: 60px;">
                <div class="card">
                    <h3>Step 1</h3>
                    <p>📋 Copy your favorite YouTube workout video link.</p>
                </div>
                <div class="card">
                    <h3>Step 2</h3>
                    <p>🔗 Paste the link into the app and set your schedule.</p>
                </div>
                <div class="card">
                    <h3>Step 3</h3>
                    <p>⏰ Get timely reminders and stay consistent with your workouts.</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --- FOOTER ---
def footer():
    st.markdown(
        """
        <div style='background-color: #111; color: white; padding: 30px; text-align: center; border-radius: 10px;'>
            <p>📧 Gmail: yourfitnessapp@gmail.com | 📞 Phone: +977-98XXXXXXXX</p>
            <p>© 2025 Your Fitness Reminder. All rights reserved.</p>
        </div>
        <br>
        """,
        unsafe_allow_html=True,
    )


# --- MAIN LANDING PAGE ---
def landing_page():
    hero_section()
    how_it_works()
    footer()
