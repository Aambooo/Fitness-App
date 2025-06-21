import sys

def check_imports():
    # Updated package list with correct import names
    packages = [
        ('streamlit', 'streamlit'),
        ('streamlit-auth0-component', 'streamlit_auth0_component'),
        ('PyJWT', 'jwt'),
        ('yt-dlp', 'yt_dlp'),
        ('mysql-connector-python', 'mysql.connector'),  # Replaced harperdb with MySQL connector
        ('python-dotenv', 'dotenv'),
        ('bcrypt', 'bcrypt'),  # Added for password hashing
        ('smtplib', 'smtplib')  # Built-in, no install needed
    ]
    
    print("Checking required packages for MySQL version...\n")
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
        
        # Additional setup note for MySQL
        print("\nAdditional setup required:")
        print("- Install XAMPP or MySQL Server")
        print("- Create a database named 'fitness_app'")
        print("- Configure your .env file with DB credentials")
    else:
        print("\nAll packages are installed correctly!")
        print("Don't forget to set up your MySQL database and .env configuration")

if __name__ == "__main__":
    check_imports()