import io, os, re
import streamlit as st
import pandas as pd
import pdfplumber
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------- Page ----------
st.set_page_config(page_title="Clinic Lab OCR → Google Sheet", page_icon="🧪", layout="wide")
st.title("🧪 Fasai Medical Clinic – Lab OCR System")

# ---------- Config / Secrets ----------
SHEET_ID = st.secrets.get("SHEET_ID", os.getenv("SHEET_ID", ""))

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

def get_gspread_client():
    # Streamlit Cloud → อ่านจาก st.secrets
    if "gcp_service_account" in st.secrets:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            dict(st.secrets["gcp_service_account"]), SCOPES
        )
    # Local/Colab → ใช้ไฟล์ service_account.json
    else:
        if not os.path.exists("service_account.json"):
            st.error("❌ Missing key: put service account in Secrets หรือวาง service_account.json ข้างไฟล์นี้")
            st.stop()
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "service_account.json", SCOPES
        )
    return gspread.authorize(creds)

def open_sheet(sheet_id: str):
    gc = get_gspread_client()
    sh = gc.open_by_key(sheet_id)
    ws = sh.sheet1
    # ถ้ายังไม่มี header ให้สร้าง
    if not ws.row_values(1):
        ws.append_row(["LN", "HN", "RESULT", "TEST"])
    return ws

# ---------- Extractors ----------
def extract_fields(text_raw: str) -> dict:
    """ดึง LN / HN / RESULT / TEST จากข้อความ"""
    t = re.sub(r"\s+", " ", text_raw.replace("\r", " ").replace("\n", " "))

    # LN เช่น: LN: 20251015-001 หรือ LN 20251015
    m_ln = re.search(r"\bLN[:\- ]+([0-9]{6,}(?:-[0-9]{1,4})?)\b", t, re.I)

    # HN เช่น: HN: H00001 หรือ HN H00001
    m_hn = re.search(r"\bHN[:\- ]+([A-Z]?\d{4,10})\b", t, re.I)

    # RESULT
    m_res = re.search(r"\b(Detected|Not\s*detected|Positive|Negative|Inconclusive)\b", t, re.I)
    if m_res:
        v = m_res.group(1).lower().replace(" ", "")
        if v in ("detected", "positive"):
            result = "Detected"
        elif v in ("notdetected", "negative"):
            result = "Not detected"
        else:
            result = "Inconclusive"
    else:
        result = "Unknown"

    return {
        "LN": m_ln.group(1) if m_ln else "",
        "HN": m_hn.group(1) if m_hn else "",
        "RESULT": result,
        "TEST": "COVID-19 (RT-PCR)",
    }

# ---------- UI ----------
st.info("Upload PDF → Extract LN, HN, RESULT, TEST → Save to Google Sheet")

files = st.file_uploader("📎 Upload Lab Reports (PDF)", type=["pdf"], accept_multiple_files=True)

# สร้าง rows ไว้ก่อนเสมอ
rows: list[dict] = []

if files:
    for f in files:
        with pdfplumber.open(io.BytesIO(f.read())) as pdf:
            text = "\n".join([(p.extract_text() or "") for p in pdf.pages])
        rows.append(extract_fields(text))

# แสดงตาราง & ปุ่มบันทึก เฉพาะเมื่อมีข้อมูล
if rows:
    df = pd.DataFrame(rows, columns=["LN", "HN", "RESULT", "TEST"])
    st.dataframe(df, use_container_width=True)

    if SHEET_ID and st.button("💾 Save to Google Sheet"):
        ws = open_sheet(SHEET_ID)
        # เขียนตามลำดับคอลัมน์ที่แน่นอน
        for r in rows:
            ws.append_row([r["LN"], r["HN"], r["RESULT"], r["TEST"]])
        st.success(f"✅ Saved {len(rows)} rows to Google Sheet!")
else:
    st.caption("Upload PDF files to start…")

st.markdown(
    f'🔗 **Sheet in use:** https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit',
    unsafe_allow_html=True
)

if rows:
    df = pd.DataFrame(rows, columns=["LN","HN","RESULT","TEST"])
    st.dataframe(df, use_container_width=True)

    if SHEET_ID and st.button("💾 Save to Google Sheet"):
        ws = open_sheet(SHEET_ID)
        before = len(ws.get_all_values())
        for r in rows:
            ws.append_row([r["LN"], r["HN"], r["RESULT"], r["TEST"]])
        after = len(ws.get_all_values())
        st.success(f"✅ Saved {after - before} rows. Now total rows (incl. header): {after}")


