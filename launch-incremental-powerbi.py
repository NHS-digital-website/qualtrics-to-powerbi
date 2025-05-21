from dotenv import load_dotenv
import os
load_dotenv()  # take environment variables from .env.
import http.client
import json
import time
import csv
import re
import pandas as pd
import requests
from io import StringIO
from datetime import datetime, timedelta, timezone

# Working but with no tests or fail safes...

def load_properties(filepath):
    props = {}
    with open(filepath, "r", encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key_value = line.split("=", 1)
            if len(key_value) == 2:
                key, value = key_value
                props[key.strip()] = value.strip()
    return props

# Load configuration once
CONFIG = load_properties("config.properties")


def connect_and_export(surveyId):
    surveyId = surveyId[0]
    print(f'Extracting: {surveyId}')

    # Try to read 'yesterday' from config.properties
    config_incrementalDay = CONFIG.get("incrementalDay")

    if config_incrementalDay:
        try:
            # Parse config value
            date_obj = datetime.strptime(config_incrementalDay, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            print(f"📅 Using 'incrementalDay' date from config.properties: {config_incrementalDay}")
        except ValueError:
            raise ValueError("Invalid date format for 'yesterday' in config.properties. Use YYYY-MM-DD.")
    else:
        # Default: calculate yesterday
        date_obj = datetime.now(timezone.utc) - timedelta(days=1)
        print(f"📅 Using default calculated 'yesterday': {date_obj.strftime('%Y-%m-%d')}")

    start_date = date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end_date = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()

    print(f"Fetching data from: {start_date} to {end_date}")

    conn = http.client.HTTPSConnection(os.getenv("qualtricsBaseUrl"))

    payload = json.dumps({
        "format": "csv",
        "compress": False,
        "useLabels": True,
        "startDate": start_date,
        "endDate": end_date
    })

    headers = {
        'Content-Type': "application/json",
        'Accept': "application/json",
        'X-API-TOKEN': os.getenv("qualtricsApiKey")
    }

    conn.request("POST", f'/API/v3/surveys/{surveyId}/export-responses', payload, headers)
    res = conn.getresponse()
    data = res.read()

    extract_progress_id(surveyId, data)

def extract_progress_id(surveyId, data):
    # Parse the JSON data
    parsed_data = json.loads(data)
    # Extract the desired string
    exportProgressId = parsed_data['result']['progressId']
    
    print(f'Progress id: {exportProgressId}')
    time.sleep(1)
    
    loop_check_completion(surveyId, exportProgressId)


def loop_check_completion(surveyId, exportProgressId):
    
    percentComplete = 0
    
    while percentComplete < 100:
        
        conn = http.client.HTTPSConnection(os.getenv("qualtricsBaseUrl"))

        headers = {
            'Accept': "application/json",
            'X-API-TOKEN': os.getenv("qualtricsApiKey")
        }

        conn.request("GET", f'/API/v3/surveys/{surveyId}/export-responses/{exportProgressId}', headers=headers)

        res = conn.getresponse()
        data = res.read()
        print(data.decode("utf-8"))
        
        parsed_data2 = json.loads(data)
        percentComplete = parsed_data2['result']['percentComplete']
        
        print(f'{percentComplete}%')
        
        time.sleep(3)
        
    fileId = parsed_data2['result']['fileId']
    
    get_survey_name(surveyId, fileId)


def get_survey_name(surveyId, fileId):
    
    conn = http.client.HTTPSConnection(os.getenv("qualtricsBaseUrl"))

    headers = {
        'Accept': "application/json",
        'X-API-TOKEN': os.getenv("qualtricsApiKey")
    }

    conn.request("GET", f"/API/v3/survey-definitions/{surveyId}", headers=headers)

    res = conn.getresponse()
    data = res.read()
    
#    print(data.decode("utf-8"))
    
    parsed_data3 = json.loads(data)
    
    Questions =  parsed_data3['result']['Questions']

    # print(Questions)

    SurveyName = parsed_data3['result']['SurveyName']
    CleanedSurveyName = re.sub(r'[^\w\s]', '_', SurveyName)
    CleanedSurveyName = CleanedSurveyName.replace(' ', '_')
    print(f'Clean Survey name: {CleanedSurveyName}')
        
    export_the_file(surveyId, fileId, CleanedSurveyName, Questions)

def mask_pii(text):
    if pd.isnull(text):
        return text
    # Mask email addresses
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '#####', text)
    # Mask 10-digit phone numbers (basic pattern)
    text = re.sub(r'\b\d{10}\b', '#####', text)
    return text

def export_the_file(surveyId, fileId, CleanedSurveyName, Questions):
    conn = http.client.HTTPSConnection(os.getenv("qualtricsBaseUrl"))

    headers = {
        'Accept': "application/octet-stream, application/json",
        'X-API-TOKEN': os.getenv("qualtricsApiKey")
    }

    conn.request("GET", f'/API/v3/surveys/{surveyId}/export-responses/{fileId}/file', headers=headers)

    res = conn.getresponse()
    data = res.read()
    utf8_encoded_data = data.decode("utf-8")

    # Read CSV
    df = pd.read_csv(StringIO(utf8_encoded_data))

    # Filter by retain columns
    retain_columns = [col.strip() for col in CONFIG.get("retainColumns").split('|')]
    filtered_df = df[[col for col in retain_columns if col in df.columns]]

    # File paths
    base_path = f"./exports/{surveyId}_{CleanedSurveyName}"
    file1 = f"{base_path}_Dailyseed_1.csv"  # Unmasked
    file2 = f"{base_path}_Dailyseed_2.csv"  # Masked

    # Save original version
    filtered_df.to_csv(file1, index=False, encoding='utf-8')
    print(f'✅ Original (unmasked) CSV saved to: {file1}')

    # Start masking process
    masked_df = filtered_df.copy()

    # Apply partial PII masking
    columns_to_mask = CONFIG.get("emailIDAndPhoneNoHashingColumns").split('|')
    for col in columns_to_mask:
        if col in masked_df.columns:
            masked_df[col] = masked_df[col].apply(mask_pii)

    # Apply conditional full replacement: replace only non-empty values with 'XXXXX'
    columns_to_replace_raw = CONFIG.get("columnsToReplaceHashCompletely", "").strip()

    if columns_to_replace_raw:
        columns_to_replace = [col.strip() for col in columns_to_replace_raw.split('|') if col.strip()]
        for col in columns_to_replace:
            if col in masked_df.columns:
                masked_df[col] = masked_df[col].apply(lambda x: '#####' if pd.notna(x) and str(x).strip() != '' else x)
   


    # Save masked version
    masked_df.to_csv(file2, index=False, encoding='utf-8')
    print(f'✅ Masked (PII filtered + conditional replacements) CSV saved to: {file2}')

    time.sleep(1)

    #get_questions(surveyId, CleanedSurveyName)
    push_to_power_bi(file2)
    

def get_access_token():
    url = f"https://login.microsoftonline.com/{os.getenv('tenantID')}/oauth2/v2.0/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'grant_type': 'client_credentials',
        'client_id': os.getenv('appClientID'),
        'client_secret': os.getenv('azureAppSecret'),
        'scope': 'https://analysis.windows.net/powerbi/api/.default'
    }

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()    
    print(f"Access Token - {response.json()['access_token']}")
    return response.json()['access_token']

def push_to_power_bi(csv_path):
    # Load CSV
    df = pd.read_csv(csv_path)

    # Convert DataFrame rows to list of dicts (Power BI format)
    rows = df.where(pd.notnull(df), None).to_dict(orient='records')

    access_token = get_access_token()

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

    

def loop_surveys():
    
    #Test with sample survey
    #surveyId = os.getenv("surveyId")
    #connect_and_export(surveyId)
    
    # Specify the CSV file path
    csv_file_path = ".surveyIDs.csv"

    # Read data from CSV file
    with open(csv_file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        # Process each line in the CSV
        for row in reader:
            # Process the line using the process_line function
            connect_and_export(row)
            time.sleep(1)
   
loop_surveys()