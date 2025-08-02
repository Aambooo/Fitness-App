import secrets
import argparse
import sys
from cryptography.fernet import Fernet

def generate_keys():
    """Generate both Flask secret key and Fernet encryption key"""
    parser = argparse.ArgumentParser(description='Generate secure cryptographic keys')
    parser.add_argument('--fernet', action='store_true', help='Generate Fernet key')
    args = parser.parse_args()
    
    print("\n🔐 Security Key Generator")
    print("="*40)
    
    # Always generate Flask secret key
    flask_key = secrets.token_hex(32)
    print(f"\nFLASK_SECRET_KEY={flask_key}")
    
    # Generate Fernet key if requested
    if args.fernet:
        fernet_key = Fernet.generate_key().decode()
        print(f"\nFERNET_KEY={fernet_key}")
    
    print("\n⚠️ Store these keys securely in your .env file!")
    print("Never commit them to version control!")

if __name__ == "__main__":
    generate_keys()