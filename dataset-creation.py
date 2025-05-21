import os
import pandas as pd
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Load the CSV
df = pd.read_csv("exports/SV_egF6Gl1rITw1udM_APIM_BAU_Feedback___Linked_Survey_FullExtract_2.csv")  # Change to your actual path

# Build the schema from CSV columns
table_name = "Qualtrics_User_Feedback"
columns = []
for col in df.columns:
    col_type = "string"
    if pd.api.types.is_numeric_dtype(df[col]):
        col_type = "Int64" if df[col].dropna().apply(float.is_integer).all() else "Double"
    columns.append({"name": col, "dataType": col_type})

dataset_definition = {
    "name": "QualtricsExport",
    "defaultMode": "Push",
    "tables": [{
        "name": table_name,
        "columns": columns
    }]
}

# Authenticate
url = f"https://login.microsoftonline.com/{os.getenv('tenantID')}/oauth2/v2.0/token"
token_data = {
    "grant_type": "client_credentials",
    "client_id": os.getenv('appClientID'),
    "client_secret": os.getenv('azureAppSecret'),
    "scope": "https://analysis.windows.net/powerbi/api/.default"
}
token_response = requests.post(url, data=token_data)
access_token = token_response.json()['access_token']

# Create the dataset
workspace_id = os.getenv("powerBIWorkspaceID")
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
create_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"

response = requests.post(create_url, headers=headers, json=dataset_definition)

if response.status_code == 201:
    print("✅ Push dataset created successfully.")
    print(response.json())
else:
    print("❌ Failed to create dataset:")
    print(response.text)


def get_powerBI_table_name():
    access_token = get_access_token()
    workspace_id = os.getenv('powerBIWorkspaceID')
    dataset_id =  os.getenv('powerBIDatasetID')
    print(f"Workspace ID: {workspace_id}")
    print(f"Dataset ID: {dataset_id}")

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/tables'

    response = requests.get(url, headers=headers)
    
    # Debugging info
    print(f"Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")

    try:
        data = response.json()
        print(data)
    except Exception as e:
        print("Failed to parse JSON:", str(e))