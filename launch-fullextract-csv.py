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
from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext

from office365.runtime.auth.authentication_context import AuthenticationContext
from office365.sharepoint.files.file import File

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
    
    conn = http.client.HTTPSConnection(os.getenv("qualtricsBaseUrl"))

    payload = "{\n  \"format\": \"csv\",\n  \"compress\": false,\n  \"useLabels\": true\n}"

    headers = {
        'Content-Type': "application/json",
        'Accept': "application/json",
        'X-API-TOKEN': os.getenv("qualtricsApiKey")
    }

    conn.request("POST", f'/API/v3/surveys/{surveyId}/export-responses', payload, headers)

    res = conn.getresponse()
    data = res.read()

    # print(data.decode("utf-8"))
    
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
    excel_path1 = f"{base_path}_FullExtract_1.xlsx"  # Unmasked    
    excel_path2 = f"{base_path}_FullExtract_2.xlsx" # Masked

    # Save original version
    filtered_df.to_excel(excel_path1, index=False, engine='openpyxl')
    print(f'✅ Excel (unmasked) saved to: {excel_path1}')

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
    masked_df.to_excel(excel_path2, index=False, engine='openpyxl')
    print(f'✅ Masked (PII filtered + conditional replacements) CSV saved to: {excel_path2}')

    time.sleep(1)

    # Check config to decide whether to push to Power BI
    push_to_power_bi_flag = CONFIG.get("pushToPowerBIWS", "no").strip().lower()
    if push_to_power_bi_flag == "yes":
        print("📤 Pushing to Power BI as per config setting.")
        push_to_power_bi(excel_path2)
    else:
        print("⏭️ Skipping Power BI push as 'pushToPowerBIWS' is not set to 'no'.") 

    create_excel_files_based_on_referer(excel_path2) 
    #push_excel_files_to_sharepoint()

# Update the push_to_power_bi function to call the new function after data is pushed
def push_to_power_bi(masked_excel_file_path):
    # Load Excel file into a DataFrame    
    df = pd.read_excel(masked_excel_file_path, engine='openpyxl')
    print(f"📤 Pushing data to Power BI from: {masked_excel_file_path}")

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

def create_excel_files_based_on_referer(masked_excel_file_path):
    # Load the masked Excel file
    df = pd.read_excel(masked_excel_file_path, engine='openpyxl')

    # Get the Referer URLs from the config file
    referer_urls = CONFIG.get("refererURLs").split('|')
    if len(referer_urls) < 3:
        print("❌ Config file must contain at least 3 Referer URLs.")
        return

    # Define output file paths
    base_path = "./exports/"
    referer_files = [
        f"{base_path}Referer_MESH.xlsx",
        f"{base_path}Referer_CIS.xlsx",
        f"{base_path}Referer_NCRS.xlsx"
    ]

    # Filter and save data for each Referer URL
    for i, url in enumerate(referer_urls):
        filtered_df = df[df['Referer'] == url]
        filtered_df.to_excel(referer_files[i], index=False, engine='openpyxl')
        print(f"✅ Excel file created for Referer '{url}' at: {referer_files[i]}")

def push_excel_files_to_sharepoint():
    """
    Pushes the generated Excel files to their respective SharePoint paths.
    """
    # Load SharePoint paths from config.properties
    sharepoint_base_url = CONFIG.get("sharepointBaseUrl")
    paths = {
        "Referer_CIS.xlsx": CONFIG.get("sharepointPathCIS"),
        "Referer_MESH.xlsx": CONFIG.get("sharepointPathMESH"),
        "Referer_NCRS.xlsx": CONFIG.get("sharepointPathNCRS"),
        "SV_egF6Gl1rITw1udM_APIM_BAU_Feedback___Linked_Survey_FullExtract_1.xlsx": CONFIG.get("sharepointPathRaw"),
        "SV_egF6Gl1rITw1udM_APIM_BAU_Feedback___Linked_Survey_FullExtract_2.xlsx": CONFIG.get("sharepointPathRaw"),
    }

    # Define the base path for the exports directory
    exports_dir = "./exports/"

    # Iterate over the files and upload them to SharePoint
    for file_name, sharepoint_path in paths.items():
        file_path = os.path.join(exports_dir, file_name)
        if os.path.exists(file_path):
            print(f"📤 Uploading '{file_name}' to SharePoint...")
            upload_to_sharepoint_with_aad(file_path, sharepoint_base_url, sharepoint_path)           
        else:
            print(f"⚠️ File '{file_name}' not found in exports directory. Skipping upload.")

def upload_to_sharepoint_with_aad(file_path, sharepoint_url, folder_path):
    """
    Uploads a file to SharePoint using Azure AD App Registration for authentication.
    """
    # Azure AD App Registration credentials
    client_id = os.getenv("sharepointClientID")
    client_secret = os.getenv("sharepointClientSecret")
    tenant_id = os.getenv("sharepointTenantID")  # Optional if using a multi-tenant app

    # Authenticate with SharePoint
    credentials = ClientCredential(client_id, client_secret)
    ctx = ClientContext(sharepoint_url).with_credentials(credentials)
    target_folder = ctx.web.get_folder_by_server_relative_url(folder_path)

    # Check if the file already exists
    file_name = os.path.basename(file_path)
    existing_files = target_folder.files
    ctx.load(existing_files)
    ctx.execute_query()

    for existing_file in existing_files:
        if existing_file.properties["Name"] == file_name:
            print(f"🔄 File '{file_name}' already exists. Deleting it...")
            existing_file.delete_object()
            ctx.execute_query()
            print(f"✅ Deleted existing file '{file_name}'.")

    # Upload the new file
    with open(file_path, "rb") as content_file:
        file_content = content_file.read()
        target_folder.upload_file(file_name, file_content).execute_query()
        print(f"✅ Uploaded '{file_name}' to SharePoint folder: {folder_path}")

def get_access_token():
    url = f"https://login.microsoftonline.com/{os.getenv('azureTenantID')}/oauth2/v2.0/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'grant_type': 'client_credentials',
        'client_id': os.getenv('azureClientID'),
        'client_secret': os.getenv('azureClientSecret'),
        'scope': 'https://analysis.windows.net/powerbi/api/.default'
    }

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()    
    print(f"Access Token - {response.json()['access_token']}")
    return response.json()['access_token']


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