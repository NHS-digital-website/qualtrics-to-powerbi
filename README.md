# qualtrics-to-powerbi

Fetch data from Qualtrics api and push it to Power BI

# Qualtrics api export list of surveys to csv file type

- Install python3 latest

- python -m install --upgrade pip

- python -m venv .venv

- pip install -r requirements.txt

- mkdir exports

- cp .sample.env .env

- Edit .env

  - update: baseUrl, apiKey and surveyId

- python launch.py
