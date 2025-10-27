import io, os, re
import streamlit as st
import pandas as pd
import pdfplumber
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Clinic Lab OCR → Google Sheet", page_icon="🧪", layout="wide")
st.title("🧪 Fasai Medical Clinic – Lab OCR System")

SHEET_ID = st.secrets.get("SHEET_ID", os.getenv("SHEET_ID", ""))

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

def get_gspread_client():
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
    else:
        if not os.path.exists("service_account.json"):
            st.error("❌ Missing key: put it in Secrets or place service_account.json here")
            st.stop()
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPES)
    return gspread.authorize(creds)

def open_sheet(sheet_id: str):
    gc = get_gspread_client()
    sh = gc.open_by_key(sheet_id)
    ws = sh.sheet1
    if not ws.row_values(1):
        ws.append_row(["LN", "HN", "RESULT", "TEST"])
    return ws

def extract_fields(text_raw: str) -> dict:
    t = re.sub(r"\s+", " ", text_raw.replace("\r", " ").replace("\n", " "))
    m_ln = re.search(r"LN[:\- ]+(\d+)", t, re.I)
    m_hn = re.search(r"HN[:\- ]+([A-Z]?\d+)", t, re.I)
    m_res = re.search(r"(Detected|Not detected|Positive|Negative|Inconclusive)", t, re.I)
    return {
        "LN": m_ln.group(1) if m_ln else "",
        "HN": m_hn.group(1) if m_hn else "",
        "RESULT": m_res.group(1) if m_res else "Unknown",
        "TEST": "COVID-19 (RT-PCR)"
    }

st.info("Upload PDF → Extract LN, HN, RESULT, TEST → Save to Google Sheet")

files = st.file_uploader("📎 Upload Lab Reports (PDF)", type=["pdf"], accept_multiple_files=True)

if files:
    rows = []
    for f in files:
        with pdfplumber.open(io.BytesIO(f.read())) as pdf:
            text = "\n".join([p.extract_text() or "" for p in pdf.pages])
        data = extract_fields(text)
        rows.append(data)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    if SHEET_ID and st.button("📥 Save to Google Sheet"):
        ws = open_sheet(SHEET_ID)
        for r in rows:
            ws.append_row(list(r.values()))
        st.success("✅ Saved to Google Sheet!")
else:
    st.caption("Upload PDF files to start...")
