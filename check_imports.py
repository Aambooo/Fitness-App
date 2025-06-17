import sys

def check_imports():
    # Package list with correct import names
    packages = [
        ('streamlit', 'streamlit'),
        ('streamlit-auth0-component', 'streamlit_auth0_component'),
        ('PyJWT', 'jwt'),
        ('yt-dlp', 'yt_dlp'),
        ('harperdb', 'harperdb'),
        ('python-dotenv', 'dotenv'),
        ('smtplib', 'smtplib')  # Built-in, no install needed
    ]
    
    print("Checking required packages...\n")
    missing = []
    
    for (pkg_name, import_name) in packages:
        try:
            __import__(import_name)
            print(f"[✓] {pkg_name} ({import_name})")
        except ImportError:
            missing.append(pkg_name)
            print(f"[✗] {pkg_name} ({import_name}) - MISSING")
    
    if missing:
        print("\nMissing packages to install:")
        for pkg in missing:
            if pkg != 'smtplib':  # smtplib is built-in
                print(f"pip install {pkg}")
    else:
        print("\nAll packages are installed correctly!")

if __name__ == "__main__":
    check_imports()