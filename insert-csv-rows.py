import os
import pandas as pd
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Load CSV
csv_path = "exports/SV_egF6Gl1rITw1udM_APIM_BAU_Feedback___Linked_Survey_2.csv"
df = pd.read_csv(csv_path)

# Convert DataFrame rows to list of dicts (Power BI format)
rows = df.where(pd.notnull(df), None).to_dict(orient='records')

# Auth again
token_url = f"https://login.microsoftonline.com/{os.getenv('tenantID')}/oauth2/v2.0/token"
token_data = {
    "grant_type": "client_credentials",
    "client_id": os.getenv('appClientID'),
    "client_secret": os.getenv('azureAppSecret'),
    "scope": "https://analysis.windows.net/powerbi/api/.default"
}
token_response = requests.post(token_url, data=token_data)
access_token = token_response.json()['access_token']

# Prepare request
dataset_id = os.getenv("powerBIDatasetID")
table_name = os.getenv("powerBITableName")
workspace_id = os.getenv("powerBIWorkspaceID")

insert_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/tables/{table_name}/rows"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Power BI accepts up to 10,000 rows at once. You can batch if needed.
payload = {"rows": rows}

response = requests.post(insert_url, headers=headers, data=json.dumps(payload))

if response.status_code == 200:
    print("✅ Data inserted into Power BI table successfully.")
else:
    print("❌ Failed to insert rows:")
    print(response.status_code, response.text)
