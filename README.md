# Clinic OCR → Google Sheet

Upload PDF → Extract LN / HN / RESULT / TEST → Save to Google Sheet (Avoid Duplicates)

## Deploy on Streamlit
1. Push to GitHub
2. On Streamlit Cloud → Advanced settings → Secrets
3. Paste this:

```toml
SHEET_ID = "1kOsBXEcJhBiJYcRt9epLnswMr8pZMlmel1jfqbhY1Xk"

[gcp_service_account]
type = "service_account"
project_id = "YOUR_PROJECT"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...key...\n-----END PRIVATE KEY-----\n"
client_email = "xxx@project.iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
