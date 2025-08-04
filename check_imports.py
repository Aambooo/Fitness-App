import sys
import platform
from typing import List, Tuple


def check_imports() -> None:
    """
    Verify all required Python packages are installed.
    Provides installation instructions for missing packages and system setup guidance.
    """
    # Package list: (PyPI name, import name, is_critical)
    packages: List[Tuple[str, str, bool]] = [
        ("streamlit", "streamlit", True),
        ("PyJWT", "jwt", True),
        ("yt-dlp", "yt_dlp", True),
        ("mysql-connector-python", "mysql.connector", True),
        ("python-dotenv", "dotenv", True),
        ("bcrypt", "bcrypt", True),
        ("pandas", "pandas", False),  # Only needed for exports
        ("dnspython", "dns", True),  # For email domain validation
        ("email-validator", "email_validator", True),
    ]

    print("\n" + "=" * 50)
    print(f"System Check (Python {sys.version.split()[0]} on {platform.system()})")
    print("=" * 50 + "\n")

    missing_critical = []
    missing_optional = []

    for pkg_name, import_name, is_critical in packages:
        try:
            __import__(import_name)
            print(f"[✓] {pkg_name.ljust(20)} ({import_name})")
        except ImportError:
            if is_critical:
                missing_critical.append(pkg_name)
                print(f"[✗] {pkg_name.ljust(20)} ({import_name}) - REQUIRED")
            else:
                missing_optional.append(pkg_name)
                print(f"[!] {pkg_name.ljust(20)} ({import_name}) - OPTIONAL")

    # Database setup check
    try:
        import mysql.connector

        conn = mysql.connector.connect(host="localhost", user="root", password="")
        print("\n[✓] MySQL Server connection successful")
        conn.close()
    except Exception as e:
        print(f"\n[✗] MySQL Connection Failed: {str(e)}")

    # Display results
    if missing_critical or missing_optional:
        print("\n" + "=" * 50)
        print("SETUP INSTRUCTIONS")
        print("=" * 50)

        if missing_critical:
            print("\nREQUIRED Packages to install:")
            for pkg in missing_critical:
                print(f"  pip install {pkg}")

        if missing_optional:
            print("\nOPTIONAL Packages (for additional features):")
            for pkg in missing_optional:
                print(f"  pip install {pkg}")

        print("\nSYSTEM REQUIREMENTS:")
        print("1. Database Setup:")
        print("   - Install MySQL Server or XAMPP")
        print("   - Create database: CREATE DATABASE fitness_app;")
        print("2. Environment Configuration:")
        print("   - Create a .env file with these required variables:")
        print("     SMTP_USER=your@gmail.com")
        print("     SMTP_PASS=your_app_password")
        print("     SECRET_KEY=your_jwt_secret")
        print("     DB_HOST, DB_USER, DB_PASSWORD, DB_NAME")
        print("3. Run database migrations if needed")
    else:
        print("\n" + "=" * 50)
        print("SYSTEM READY FOR DEVELOPMENT")
        print("=" * 50)
        print("\nAll dependencies are installed correctly!")
        print("Next steps:")
        print("- Configure your .env file with SMTP and DB credentials")
        print("- Run the application with: streamlit run app.py")


if __name__ == "__main__":
    check_imports()
    print("\nTip: For Windows users, ensure MySQL is added to your PATH")
