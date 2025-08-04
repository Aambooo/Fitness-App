import secrets
import argparse
import sys
from cryptography.fernet import Fernet


def generate_keys():
    """Generate secure cryptographic keys for the application"""
    parser = argparse.ArgumentParser(
        description="Generate secure keys for your fitness application",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--fernet",
        action="store_true",
        help="Generate a Fernet encryption key (for advanced security)",
    )
    parser.add_argument(
        "--all", action="store_true", help="Generate all recommended keys"
    )
    args = parser.parse_args()

    print("\n🔐 Fitness App Key Generator")
    print("=" * 40)

    # Generate JWT secret key (required)
    jwt_key = secrets.token_hex(32)
    print(f"\nSECRET_KEY={jwt_key}  # For JWT token generation")

    # Generate Flask secret key if requested
    if args.all:
        flask_key = secrets.token_hex(32)
        print(f"\nFLASK_SECRET_KEY={flask_key}  # For session security")

    # Generate Fernet key if requested
    if args.fernet or args.all:
        fernet_key = Fernet.generate_key().decode()
        print(f"\nFERNET_KEY={fernet_key}  # For data encryption")

    print("\n⚠️ Security Best Practices:")
    print("- Store these keys in your .env file")
    print("- Never commit .env to version control")
    print("- Restrict file permissions (chmod 600 .env)")
    print("- Regenerate keys if compromised")
    print("- Use different keys for development and production")


if __name__ == "__main__":
    generate_keys()
