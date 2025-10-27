import io, os, re
from datetime import datetime, timezone, timedelta

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
    """เปิดชีตและสร้างหัวตารางถ้ายังไม่มี (รวม Approved Date Time)"""
    gc = get_gspread_client()
    sh = gc.open_by_key(sheet_id)
    ws = sh.sheet1
    header = ws.row_values(1)
    wanted_header = ["LN", "HN", "RESULT", "TEST", "Approved Date Time"]
    if not header:
        ws.append_row(wanted_header)
    elif header != wanted_header:
        # ถ้าอยาก “คงหัวเดิม” ให้ลบบล็อก 3 บรรทัดล่างนี้ออก
        ws.delete_rows(1)
        ws.insert_row(wanted_header, 1)
    return ws

# ---------- OCR Extractors ----------
def extract_fields(text_raw: str) -> dict:
    """ดึง LN / HN / RESULT / TEST / Approved Date Time จากข้อความ PDF"""
    # รวมบรรทัดเป็นบรรทัดเดียวเพื่อให้ regex ค้นง่าย
    t = re.sub(r"\s+", " ", text_raw.replace("\r", " ").replace("\n", " "))

    # LN เช่น: LN: 20251015-001 หรือ LN 20251015
    m_ln = re.search(r"\bLN[:\- ]+([0-9]{6,}(?:-[0-9]{1,4})?)\b", t, re.I)

    # HN เช่น: H00001
    m_hn = re.search(r"\bHN[:\- ]+([A-Z]?\d{4,10})\b", t, re.I)

    # RESULT เช่น Detected / Not detected / Positive / Negative / Inconclusive
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

    # Approved Date Time เช่น "Approved Date Time: 16/10/2025 09:26:21"
    # รองรับทั้งแบบมีวินาที และไม่มีวินาที
    approved_str = ""
    m_ap = re.search(
        r"Approved\s*Date\s*Time[:\- ]+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}(?::\d{2})?)",
        t, re.I
    )
    if m_ap:
        raw = f"{m_ap.group(1)} {m_ap.group(2)}"
        # พยายาม parse 2 รูปแบบ
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                approved_dt = datetime.strptime(raw, fmt)
                approved_str = approved_dt.strftime("%d/%m/%Y %H:%M")
                break
            except ValueError:
                continue
    # ถ้าอยาก fallback เป็นเวลาปัจจุบันของไทย ให้ปลดคอมเมนต์ 2 บรรทัดล่างนี้
    # else:
    #     approved_str = datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M")

    return {
        "LN": m_ln.group(1) if m_ln else "",
        "HN": m_hn.group(1) if m_hn else "",
        "RESULT": result,
        "TEST": "COVID-19 (RT-PCR)",
        "Approved Date Time": approved_str,
    }

# ---------- UI ----------
st.info("Upload PDF → Extract LN, HN, RESULT, TEST, Approved Date Time → Save to Google Sheet")

files = st.file_uploader("📎 Upload Lab Reports (PDF)", type=["pdf"], accept_multiple_files=True)

# รวมผล OCR
rows: list[dict] = []
if files:
    for f in files:
        with pdfplumber.open(io.BytesIO(f.read())) as pdf:
            text = "\n".join([(p.extract_text() or "") for p in pdf.pages])
        rec = extract_fields(text)   # ✅ ตอนนี้ Approved Date Time มาจาก PDF แล้ว
        rows.append(rec)

# ลิงก์ไปชีตที่ใช้อยู่
st.markdown(
    f'🔗 **Sheet in use:** https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit',
    unsafe_allow_html=True
)

# ---------- ตาราง + ปุ่ม ----------
if rows:
    df = pd.DataFrame(rows, columns=["LN", "HN", "RESULT", "TEST", "Approved Date Time"])
    st.dataframe(df, use_container_width=True)

    # ปุ่มบันทึก
    if SHEET_ID and st.button("💾 Save to Google Sheet", key="save_btn"):
        ws = open_sheet(SHEET_ID)
        before = len(ws.get_all_values())
        for r in rows:
            ws.append_row([r["LN"], r["HN"], r["RESULT"], r["TEST"], r["Approved Date Time"]])
        after = len(ws.get_all_values())
        st.success(f"✅ Saved {after - before} rows. Now total rows (incl. header): {after}")

    # ปุ่มทดสอบเขียน/อ่านกลับ
    if SHEET_ID and st.button("🧪 Test write & read back", key="test_btn"):
        ws = open_sheet(SHEET_ID)
        ws.append_row(["TEST-LN","TEST-HN","Detected","COVID-19 (RT-PCR)","01/01/2025 12:00"])
        values = ws.get_all_values()
        st.success(f"Rows in sheet (including header): {len(values)}")
        st.write("Last 5 rows from Google Sheet:")
        st.table(values[-5:])
else:
    st.caption("Upload PDF files to start…")
