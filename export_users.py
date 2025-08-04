"""
User data export utility
Exports all users to CSV with enhanced security and data handling
"""

import pandas as pd
from database_service import dbs
from datetime import datetime
import os
import logging
from typing import Tuple, Optional
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("user_export.log", mode="a"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def secure_filename(base: str) -> str:
    """Generate a secure filename with hash suffix"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hash_suffix = hashlib.sha256(timestamp.encode()).hexdigest()[:8]
    return f"{base}_{timestamp}_{hash_suffix}.csv"


def sanitize_data(df: pd.DataFrame) -> pd.DataFrame:
    """Remove or mask sensitive user data"""
    # Remove sensitive columns completely
    sensitive_cols = ["password_hash", "google_id", "auth_token"]
    for col in sensitive_cols:
        if col in df.columns:
            del df[col]

    # Mask email domains (optional)
    if "email" in df.columns:
        df["email"] = df["email"].apply(lambda x: x[0] + "***" + x[x.find("@") :])

    return df


def export_users(output_dir: str = "user_exports") -> Tuple[bool, Optional[str]]:
    """
    Export all users to CSV with enhanced security measures

    Args:
        output_dir: Directory to save exports (default: 'user_exports')

    Returns:
        Tuple (success: bool, file_path: str or None)
    """
    try:
        # Secure directory creation
        os.makedirs(output_dir, exist_ok=True)
        os.chmod(output_dir, 0o700)  # More restrictive permissions

        logger.info("Fetching user data...")
        users = dbs.get_all_users()

        if not users:
            logger.warning("No users found in database")
            return False, None

        df = pd.DataFrame(users)

        # Data sanitization
        df = sanitize_data(df)

        # Add export metadata
        df["_export_meta"] = f"Exported at {datetime.now().isoformat()}"
        df["_export_version"] = "1.1"

        # Generate secure filename
        filename = secure_filename("users")
        filepath = os.path.join(output_dir, filename)

        # Export with validation
        df.to_csv(filepath, index=False, encoding="utf-8-sig")

        # Post-export verification
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise IOError("Export file verification failed")

        # Set file permissions (owner read/write only)
        os.chmod(filepath, 0o600)

        logger.info(f"Successfully exported {len(df)} users to {filepath}")
        return True, filepath

    except Exception as e:
        logger.error(f"Export failed: {str(e)}", exc_info=True)
        # Clean up potentially partial files
        if "filepath" in locals() and os.path.exists(filepath):
            os.remove(filepath)
        return False, None


if __name__ == "__main__":
    logger.info("=== Starting user data export ===")
    success, path = export_users()

    if success:
        logger.info(f"Export completed successfully: {path}")
        print(f"Export saved to: {path}")  # User-friendly output
    else:
        logger.error("Export process failed")
        print("Export failed - check logs for details")

    exit(0 if success else 1)
