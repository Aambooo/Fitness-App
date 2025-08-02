"""
User data export utility
Exports all users to CSV with proper data handling
"""

import pandas as pd
from database_service import dbs
from datetime import datetime
import os
import logging
from typing import Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def export_users(output_dir: str = "exports") -> Tuple[bool, Optional[str]]:
    """
    Export all users to CSV with proper data sanitization
    
    Args:
        output_dir: Directory to save exports (default: 'exports')
        
    Returns:
        Tuple (success: bool, file_path: str or None)
    """
    try:
        # Create secure output directory
        os.makedirs(output_dir, exist_ok=True)
        os.chmod(output_dir, 0o755)  # Restrict permissions
        
        logging.info("Fetching user data from database...")
        users = dbs.get_all_users()
        
        if not users:
            logging.warning("No users found in database")
            return False, None
            
        # Convert to DataFrame
        df = pd.DataFrame(users)
        
        # Data sanitization
        sensitive_columns = ['password_hash', 'google_id', 'token']
        for col in sensitive_columns:
            if col in df.columns:
                df[col] = 'REDACTED'
        
        # Add export metadata
        df['_export_timestamp'] = datetime.now().isoformat()
        
        # Generate secure filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"users_export_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        # Export with validation
        df.to_csv(filepath, index=False)
        
        # Verify export
        if not os.path.exists(filepath):
            raise FileNotFoundError("Export file not created")
            
        logging.info(f"Successfully exported {len(users)} users to {filepath}")
        return True, filepath
        
    except Exception as e:
        logging.error(f"Export failed: {str(e)}", exc_info=True)
        return False, None

if __name__ == "__main__":
    logging.info("Starting user data export...")
    success, path = export_users()
    
    if success:
        logging.info(f"Export completed: {path}")
        exit(0)
    else:
        logging.error("Export failed")
        exit(1)