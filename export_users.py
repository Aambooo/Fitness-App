import pandas as pd
from database_service import db, SCHEMA, USERS_TABLE

# 1. Fetch all user data
print("Fetching user data...")
users = db.sql(f"SELECT * FROM `{SCHEMA}`.`{USERS_TABLE}`")

# 2. Convert to DataFrame and export
df = pd.DataFrame(users)
df.to_csv('users_export.csv', index=False)
print(f"Successfully exported {len(users)} records to users_export.csv")