# qualtrics-to-powerbi

Fetch data from Qualtrics API and push it to Power BI and Sharepoint using REST API

# Qualtrics API export list of surveys to excel file type and push it to Power BI and Sharepoint

- Install python3 latest

- python -m install --upgrade pip

- python -m venv .venv

- pip install -r requirements.txt

- mkdir exports

- cp .sample.env .env

- Edit .env

  - update: baseUrl, apiKey and surveyId

- python launch-fullextract-csv.py - This is to load full extract data from qualtrics to power BI and sharepoint

- python launch-incremental-powerbi.py - This is to load incremental updates from qualtrics to power BI

# Qualtrics Full extract to Sharepoint & Power BI(Optional) - Daily [launch-fullextract-csv.py]:

### **Overview of the Script**

This Python script automates the process of exporting survey data from Qualtrics, processing it, and integrating it with Power BI and SharePoint. Below are the key functionalities:

- **Environment and Configuration Setup**:

  - Loads environment variables from a .env file (e.g., API keys, Azure AD credentials).
  - Reads configuration settings from a config.properties file for dynamic behavior.

- **Survey Data Export**:

  - Reads survey IDs from a .surveyIDs.csv file.
  - For each survey ID:
    - Initiates the export process by making API calls to the Qualtrics API.
    - Tracks the export progress using a `progressId`.
    - Downloads the exported survey data as a CSV file once the export is complete.

- **Data Processing**:

  - Filters the survey data to retain only specific columns defined in the configuration.
  - Saves two versions of the data:
    - **Unmasked Version**: Original data.
    - **Masked Version**: Applies masking to sensitive data (e.g., email addresses, phone numbers) based on configuration settings.

- **Power BI Integration**:

  - Optionally pushes the masked data to Power BI if configured (pushToPowerBIWS is set to "yes").
  - Converts the data into a format suitable for Power BI and sends it to a specified dataset and table.

- **Excel File Creation**:

  - Creates three Excel files (`Referer_MESH.xlsx`, `Referer_CIS.xlsx`, `Referer_NCRS.xlsx`) based on the `Referer` column in the masked data.
  - Saves the files in the exports directory.

- **SharePoint Integration**:

  - Uploads the generated Excel files to specific SharePoint paths using Azure AD App Registration for authentication.
  - Deletes existing files with the same name in the SharePoint directory before uploading the new files.

- **Incremental Data Export**:

  - Supports incremental data export by specifying a date range (e.g., "yesterday") from the config.properties file or calculating it dynamically.

- **Helper Functions**:

  - `mask_pii`: Masks personally identifiable information (PII) like email addresses and phone numbers.
  - `get_access_token`: Retrieves an access token for Power BI API calls using Azure AD credentials.
  - `upload_to_sharepoint_with_aad`: Authenticates with SharePoint using Azure AD and uploads files.
  - `load_properties`: Reads key-value pairs from the config.properties file.

- **Execution Flow**:
  - The `loop_surveys` function orchestrates the entire process:
    - Reads survey IDs.
    - Exports survey data.
    - Processes the data.
    - Pushes data to Power BI.
    - Creates Excel files based on the `Referer` column.
    - Uploads the files to SharePoint.

---

### **How to Use**

1. **Setup**:

   - Add your environment variables to a .env file (e.g., API keys, Azure AD credentials).
   - Configure the config.properties file with the required settings (e.g., columns to retain, columns to mask, incremental date, SharePoint paths).

2. **Run the Script**:

   - Place the survey IDs in a .surveyIDs.csv file.
   - Execute the script to export, process, and upload the data.

3. **Output**:
   - Processed Excel files are saved in the exports directory.
   - Data is pushed to Power BI if configured.
   - Excel files are uploaded to SharePoint paths specified in the configuration.

---

# Qualtrics incremental updates to PowerBI - Daily [launch-incremental-powerbi.py]:

### **Overview of the Script**

This Python script automates the process of exporting survey data from Qualtrics, processing it, and integrating it with Power BI. Below are the key functionalities:

- **Environment and Configuration Setup**:

  - Loads environment variables from a .env file.
  - Reads configuration settings from a config.properties file for dynamic behavior.

- **Survey Data Export**:

  - Reads survey IDs from a .surveyIDs.csv file.
  - For each survey ID:
    - Initiates the export process by making API calls to the Qualtrics API.
    - Tracks the export progress using a `progressId`.
    - Downloads the exported survey data as a CSV file once the export is complete.

- **Data Processing**:

  - Filters the survey data to retain only specific columns defined in the configuration.
  - Saves two versions of the data:
    - **Unmasked Version**: Original data.
    - **Masked Version**: Applies masking to sensitive data (e.g., email addresses, phone numbers) based on configuration settings.

- **Power BI Integration**:

  - Pushes the masked data to Power BI using the Power BI REST API.
  - Converts the data into a format suitable for Power BI and sends it to a specified dataset and table.

- **Excel File Creation**:

  - Creates two Excel files for each survey:
    - `Dailyseed_1.xlsx`: Unmasked version.
    - `Dailyseed_2.xlsx`: Masked version with PII filtering and conditional replacements.

- **Incremental Data Export**:

  - Supports incremental data export by specifying a date range (e.g., "yesterday") from the config.properties file or calculating it dynamically.

- **Helper Functions**:

  - `mask_pii`: Masks personally identifiable information (PII) like email addresses and phone numbers.
  - `get_access_token`: Retrieves an access token for Power BI API calls using Azure AD credentials.
  - `load_properties`: Reads key-value pairs from the config.properties file.

- **Execution Flow**:
  - The `loop_surveys` function orchestrates the entire process:
    - Reads survey IDs.
    - Exports survey data.
    - Processes the data.
    - Pushes data to Power BI.
    - Saves the processed data as Excel files.

---

### **How to Use**

1. **Setup**:

   - Add your environment variables to a .env file (e.g., API keys, Azure AD credentials).
   - Configure the config.properties file with the required settings (e.g., columns to retain, columns to mask, incremental date).

2. **Run the Script**:

   - Place the survey IDs in a .surveyIDs.csv file.
   - Execute the script to export, process, and upload the data.

3. **Output**:
   - Processed Excel files are saved in the exports directory.
   - Data is pushed to Power BI if configured.

---
