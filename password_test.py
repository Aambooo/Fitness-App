from auth import auth_service
from database_service import dbs
import bcrypt
from dotenv import load_dotenv
import secrets
import string

# 1. FIRST initialize database service
print("\n🔧 Initializing Database Service...")
dbs._create_connection_pool()  # Force connection pool creation

# 2. THEN configure auth service
print("🔧 Configuring Auth Service...")
auth_service.dbs = dbs

# Verification
print("\n🔍 Service Verification:")
print(f"Auth DBS set: {auth_service.dbs is not None}")
print(f"DBS pool active: {dbs.connection_pool is not None}")


def generate_random_password():
    """Generate a secure random 12-character password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def run_test():
    print("\n🔥 ENHANCED NUCLEAR TEST 🔥")

    # Test credentials
    test_email = "nabdabop10@gmail.com"
    test_password = "Okxata123456"

    # Generate token using the properly configured auth_service
    token = auth_service.generate_token(test_email)
    print(f"Token: {token}")
    print(f"Testing with password: {test_password}")

    # Verify database connection is set
    if not auth_service.dbs:
        print("❌ CRITICAL: Database service not initialized!")
        return False

    # Test password reset
    result = auth_service.reset_password(token, test_password)
    print(f"\nReset result: {result}")

    # Immediate verification
    if result:
        user = dbs.get_user_by_email(test_email)
        if user:
            print("\n🔍 VERIFICATION:")
            print(f"Stored hash: {user['password_hash'][:60]}...")
            is_valid = bcrypt.checkpw(
                test_password.encode("utf-8"), user["password_hash"].encode("utf-8")
            )
            print(f"Password matches: {is_valid}")
            return is_valid
    return False


if __name__ == "__main__":
    success = run_test()
    print("\n✅ TEST COMPLETE" if success else "❌ TEST FAILED")
