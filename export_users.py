import pandas as pd
from database_service import dbs
from datetime import datetime
import os

def export_users(output_dir: str = "exports"):
    """
    Export all users to CSV from MySQL database
    Args:
        output_dir: Directory to save the export file (default: 'exports')
    Returns:
        Tuple (success: bool, file_path: str)
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Fetch all user data
        print("Fetching user data from MySQL...")
        
        # We'll need to implement get_all_users() in database_service.py
        users = dbs.get_all_users()  
        
        if not users:
            print("No users found in database")
            return False, None
            
        # 2. Convert to DataFrame
        df = pd.DataFrame(users)
        
        # Clean up sensitive data (just in case)
        if 'password_hash' in df.columns:
            df = df.drop(columns=['password_hash'])
        
        # 3. Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"users_export_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        # 4. Export to CSV
        df.to_csv(filepath, index=False)
        print(f"Successfully exported {len(users)} records to {filepath}")
        return True, filepath
        
    except Exception as e:
        print(f"Export failed: {str(e)}")
        return False, None

if __name__ == "__main__":
    success, filepath = export_users()
    if not success:
        exit(1)