import io
import os
import json
import base64
from datetime import datetime
import requests as http_requests
from google import genai
from pydantic import BaseModel, Field
import sys
import uuid
from dotenv import load_dotenv
from docxtpl import DocxTemplate, RichText
from typing import List, Optional
import ast
import re
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Header, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber

from pythainlp.util import bahttext  # pip install pythainlp

# บังคับใช้ UTF-8 สำหรับการแสดงผลบน Terminal
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

# ตั้งค่าโมเดล Gemini
GEMINI_API_KEY = os.environ.get("API_KEY") or os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)
print(f"[DEBUG] GEMINI_API_KEY loaded: {bool(GEMINI_API_KEY)}")

# =================================================================
# การตั้งค่า External Authentication API
# =================================================================
EXTERNAL_AUTH_LOGIN_URL = os.environ.get(
    "EXTERNAL_AUTH_LOGIN_URL",
    "https://service.mangoanywhere.com/api/public/Login"
    
)

MAINCODE = os.environ.get("MAINCODE", "MANGO")
EXTERNAL_QUOTATION_URL = os.environ.get(
    "EXTERNAL_QUOTATION_URL",
    "https://service.mangoanywhere.com/Anywhere/BD/QO_ReadData"
)

class LoginRequest(BaseModel):
    userid: str
    userpass: str

class quotation(BaseModel):
    quotation_id: str
    result_quotation: dict
    dbd_data: Optional[dict] = None

class CleanItem(BaseModel):
    item_name: str
    quantity: float
    unit: str
    price: float
    remark: Optional[str] = None

class CleanPaymentTerm(BaseModel):
    period: str
    description: str
    amount: float

class CleanQuotationData(BaseModel):
    quotation_id: str
    quotation_date: str
    customer_name: str
    customer_address: str
    total_amount: float
    products_and_services: List[CleanItem]
    payment_terms: List[CleanPaymentTerm]
    terms_and_conditions: str

# =================================================================
# Helper: แยก JSON จาก Qwen response
# =================================================================
def extract_json_from_qwen_response(response_text: str) -> str:
    print(f"[DEBUG] extract_json_from_qwen_response start, raw len={len(response_text)}")
    if '```json' in response_text:
        parts = response_text.split('```json', 1)[1].split('```', 1)
        if parts:
            return parts[0].strip()
    if '```' in response_text:
        parts = response_text.split('```', 2)
        if len(parts) >= 3:
            candidate = parts[1].strip()
            if candidate.lower().startswith('json'):
                candidate = candidate.split('\n', 1)[1].strip() if '\n' in candidate else candidate
            return candidate
    start = response_text.find('{')
    if start != -1:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(response_text)):
            ch = response_text[idx]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return response_text[start:idx+1].strip()
    return response_text.strip()

def repair_truncated_json(text: str) -> str:
    # ซ่อม JSON ที่โมเดลตอบกลับมาไม่ครบ เช่น ขาด } หรือ ] ปิดท้าย
    # (gemini-3.5-flash ใน JSON mode ตัด } ตัวสุดท้ายหายเป็นบางครั้ง)
    stack = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in '{[':
            stack.append(ch)
        elif ch in '}]':
            if stack:
                stack.pop()
    if in_string:
        text += '"'
    text = re.sub(r",\s*$", "", text)
    for ch in reversed(stack):
        text += '}' if ch == '{' else ']'
    return text

def try_parse_json(text: str):
    text = (text or '').strip()
    if not text:
        raise json.JSONDecodeError("Empty response", text, 0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        repaired = repair_truncated_json(text)
        if repaired != text:
            print(f"[DEBUG] repair_truncated_json — เติมส่วนปิดท้ายที่หายไป ({len(repaired) - len(text)} ตัวอักษร)")
            return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(text)
    except Exception:
        pass
    try:
        s = text
        if '"' not in s and "'" in s:
            s = s.replace("'", '"')
        s = re.sub(r",\s*([}\]])", r"\1", s)
        return json.loads(s)
    except Exception as e:
        raise json.JSONDecodeError(str(e), text, 0)

# =================================================================
# Clean and filter quotation data Json
# =================================================================
def filter_and_clean_quotation(raw_json: dict) -> CleanQuotationData:
    data = raw_json.get("data", {})
    header = data.get("header", {})
    details = data.get("detail", [])
    detail3 = data.get("detail3", [])
    detail4 = data.get("detail4", [])

    address_parts = [
        header.get("address1", ""),
        header.get("address2", ""),
        header.get("address3", "")
    ]
    full_address = " ".join([p for p in address_parts if p]).strip()

    amount = header.get("amount", 0.0)
    discount = header.get("total_discount", 0.0)
    vat = header.get("vat_amount", 0.0)

    clean_items = []
    for item in details:
        name = item.get("type_name")
        if name:
            price = item.get("sell_amount") or 0.0
            clean_items.append(CleanItem(
                item_name=name.strip(),
                quantity=item.get("qty", 0.0),
                unit=item.get("unitname", ""),
                price=price,
                remark=item.get("mat_other")
            ))

    clean_payment_terms = []
    for term in detail4:
        clean_payment_terms.append(CleanPaymentTerm(
            period=term.get("desc_period", ""),
            description=term.get("description", ""),
            amount=term.get("amt", 0.0)
        ))

    tnc_lines = [d.get("remark", "") for d in detail3 if d.get("remark")]
    full_tnc_text = "\n".join(tnc_lines)

    docno = header.get("docno", "")
    rev = header.get("revno", "")

    if not rev:
        qu_id = docno  # ถ้าไม่มี rev ให้ใช้ docno อย่างเดียว
    else:
        qu_id = f"{docno}.R{rev}"  # สร้างรหัสใบเสนอราคาแบบง่ายๆ

    return CleanQuotationData(
        quotation_id=qu_id,
        quotation_date=header.get("docdate", ""),
        customer_name=header.get("customer_name", ""),
        customer_address=full_address,
        total_amount=amount - discount + vat,
        products_and_services=clean_items,
        payment_terms=clean_payment_terms,
        terms_and_conditions=full_tnc_text
    )

# =================================================================
# Helper: แยกข้อมูลจากไฟล์ DBD PDF ด้วย pdfplumber (structured)
# =================================================================
def _clean_text(text: str) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()

def extract_dbd_profile(file_bytes: bytes) -> dict:
    raw_rows = []
    header_text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            if i == 0:
                header_text = page.extract_text() or ""
            for table in page.extract_tables():
                raw_rows.extend(table)

    data = {}
    for row in raw_rows:
        if len(row) < 2:
            continue
        label = _clean_text(row[0]).rstrip(":").strip()
        value = row[1] if row[1] is not None else ""
        data[label] = value

    company_name = None
    m = re.search(r"ข้อมูล\s*\n(.+)", header_text)
    if m:
        company_name = _clean_text(m.group(1))

    directors_raw = data.get("กรรมการ", "")
    directors_list = []
    for line in directors_raw.split("\n"):
        line = line.strip().rstrip("/").strip()
        if not line:
            continue
        line = re.sub(r"^\d+\.\s*", "", line)
        directors_list.append(line)

    return {
        "company_name": company_name or _clean_text(data.get("ชื่อนิติบุคคล", "")),
        "registration_number": _clean_text(data.get("เลขทะเบียนนิติบุคคล", "")),
        "address": _clean_text(data.get("ที่ตั้ง", "")),
        "directors": directors_list,
        "signing_authority": _clean_text(data.get("คณะกรรมการลงชื่อผูกพัน", "")).rstrip("/").strip(),
    }

def parse_dbd_pdf(file_bytes: bytes) -> dict:
    structured = extract_dbd_profile(file_bytes)
    print("=" * 60)
    print("[DBD] ===== ข้อมูลที่ดึงจากไฟล์ DBD =====")
    print(f"  company_name       : {structured.get('company_name')}")
    print(f"  registration_number: {structured.get('registration_number')}")
    print(f"  address            : {structured.get('address')}")
    print(f"  directors          : {structured.get('directors')}")
    print(f"  signing_authority  : {structured.get('signing_authority')}")
    print("=" * 60)
    return structured

# =================================================================
# ฟังก์ชันสกัดข้อมูลจากเอกสารด้วย Gemini
# =================================================================
def analyze_with_gemini(parsed_json, dbd_profile: dict = None):
    if isinstance(parsed_json, BaseModel):
        try:
            model_data = parsed_json.model_dump()
        except Exception:
            try:
                model_data = json.loads(parsed_json.json())
            except Exception:
                model_data = {}
        document_content = json.dumps(model_data, ensure_ascii=False, indent=2)
    else:
        document_content = json.dumps(parsed_json, ensure_ascii=False, indent=2)

    dbd_section = ""
    if dbd_profile:
        dbd_section = f"""
    ── ข้อมูลจากหนังสือรับรองบริษัท (DBD) ──────────────────────────────
    ข้อมูลต่อไปนี้ดึงมาจาก DBD อย่างเป็นทางการ ให้ใช้แทนข้อมูลใบเสนอราคาสำหรับ field Licensee_* ทุกตัว:

    {json.dumps(dbd_profile, ensure_ascii=False, indent=2)}

    วิธีแมป:
    - "company_name"        -> Licensee_company_name
    - "registration_number" -> Licensee_tax_id
    - "address"             -> Licensee_address
    - Licensee_authorized_person: ให้อ่าน "signing_authority" เป็นหลัก แล้วพิจารณาดังนี้

        [กรณีที่ 1] signing_authority ระบุชื่อบุคคลโดยตรง เช่น "นายสมชาย ใจดี ลงลายมือชื่อ..."
        → ใช้ชื่อนั้นเลย ไม่ต้องดู directors

        [กรณีที่ 2] signing_authority บอกจำนวนที่ต้องลงนาม แต่ไม่ระบุชื่อ → ดึงชื่อทั้งหมดจาก directors แล้วเชื่อมตามเงื่อนไขนี้:

        หลักการ: นับจำนวนที่ต้องลงนาม (X) จาก signing_authority แล้วเทียบกับจำนวน directors ทั้งหมด (N)
        - ถ้า X < N (ต้องลงนาม น้อยกว่า จำนวนกรรมการทั้งหมด)
          → แปลว่า "ใครก็ได้" → เอาชื่อกรรมการ **ทั้งหมด** จาก directors เชื่อมด้วย " หรือ "
          ตัวอย่าง: X=1, directors=[A, B] → "A หรือ B"
          ตัวอย่าง: X=2, directors=[A, B, C, D] → "A หรือ B หรือ C หรือ D"
        - ถ้า X == N (ต้องลงนาม เท่ากับ จำนวนกรรมการทั้งหมด)
          → แปลว่า "ทุกคนต้องลงนาม" → เอาชื่อกรรมการ **ทั้งหมด** จาก directors เชื่อมด้วย " และ "
          ตัวอย่าง: X=2, directors=[A, B] → "A และ B"
        - ถ้า directors มีคนเดียว → ใช้ชื่อนั้นเลย ไม่ต้องเชื่อม

        รูปแบบที่ต้องแปลงเป็น X:
        "หนึ่งคน" หรือ "คนเดียว" → X=1
        "สองคน" → X=2, "สามคน" → X=3, "สี่คน" → X=4
        "หนึ่งในสองคน" → X=1, N=2
        "สองในสี่คน" → X=2, N=4
        "สามในห้าคน" → X=3, N=5

        [กรณีที่ 3] signing_authority ว่างหรือไม่มีข้อมูล และ directors ว่างเปล่า
        → ใส่ค่าว่าง ""
    ─────────────────────────────────────────────────────────────────────
"""

    prompt = f"""
    นี่คือข้อมูลใบเสนอราคาจากระบบ (JSON Format):
    {document_content}
    {dbd_section}

    หน้าที่ของคุณคือ สกัดข้อมูลจากใบเสนอราคานี้ตามหัวข้อที่กำหนด และต้องตอบกลับมาในรูปแบบ JSON เท่านั้น

    [กฎข้อบังคับที่ต้องทำตามอย่างเคร่งครัด]
    1. ห้ามมีข้อความเกริ่นนำ ข้อความสรุป หรือคำอธิบายใดๆ ทั้งสิ้น ให้ตอบกลับมาแค่โครงสร้างปีกกา {{...}} ของ JSON เท่านั้น
    2. หากหัวข้อไหนไม่พบข้อมูลในเอกสาร ให้ใส่ค่าเป็นค่าว่าง "" (empty string) เท่านั้น ห้ามใส่ null, ห้ามข้ามฟิลด์นั้น (ยังต้องมี key ครบทุกตัว)
    3. ใช้ชื่อ Key ตามที่ระบุด้านล่างนี้เป๊ะๆ ห้ามเปลี่ยนชื่อ Key โดยเด็ดขาด
    4. ห้ามแต่งเติมข้อมูลที่ไม่มีในเอกสารเด็ดขาด
    5. "unit" และ "quantity" ต้องพิจารณาร่วมกัน: ถ้า quantity=12 และ unit=month ให้คิดว่าเป็น 1 ปี
    6. Field ราคา "รายเดือน" vs "รายปี" ให้ใส่ "-" (ขีด) เมื่อรูปแบบการชำระนั้นไม่ได้ถูกเลือก เช่น
       - ถ้าลูกค้าซื้อแบบ "รายปี"   → field _month_price / _month_rows_X ทั้งหมดให้ใส่ "-"
       - ถ้าลูกค้าซื้อแบบ "รายเดือน" → field _year_price / _year_rows_X ทั้งหมดให้ใส่ "-"
       - กฎนี้ใช้กับทุก field ที่มีคำว่า month หรือ year ใน Key ยกเว้น Contract_date และ Quotation_date
    7. ตัวเลขราคาหรือจำนวนเงินทั้งหมด ต้องใส่เครื่องหมายจุลภาค (,) คั่นหลักพัน (เช่น 10,000)
    8. User_with_program กับ Free_user_count ต้องแยกออกจากกันอย่างชัดเจน
    ── ข้อมูลสัญญาและคู่สัญญา ──────────────────────────────────────────

    "Contract_id"               : สัญญาเลขที่
    "Contract_date"             : วันที่ทำสัญญา รูปแบบ "1 มกราคม 2567"
    "Licensee_company_name"     : ชื่อบริษัทลูกค้า (ผู้รับอนุญาต)
    "Licensee_tax_id"           : เลขทะเบียนนิติบุคคลของบริษัทลูกค้า
    "Licensee_directors"        : รายชื่อกรรมการผู้มีอำนาจลงนามฝั่งผู้รับอนุญาต
    "Licensee_authorized_person": ชื่อกรรมการบริษัท หรือผู้รับมอบอำนาจของบริษัทลูกค้า 
    "Licensee_address"          : ที่ตั้งสำนักงานของบริษัทลูกค้า

    ── ค่าสิทธิ์การใช้โปรแกรม (License fee) ───────────────────────────

    "Software_product_name"        : ชื่อโปรแกรม เช่น Mango Anywhere Software หรือ Mango Project Management "PPN"
    "Standard_modules_total"       : จำนวน Module มาตรฐานที่มาพร้อมโปรแกรม (ตัวเลข)
    "Total_users_count"            : จำนวนผู้ใช้งานทั้งหมด รวมมาตรฐานและเพิ่มเติม (ตัวเลข)
    "Total_multi_company_count"    : จำนวนบริษัทในเครือทั้งหมด ถ้าไม่มีให้ใส่ 0 (ตัวเลข)
    "Total_optional_modules_count" : จำนวนระบบโมดูลเสริมทั้งหมด (ตัวเลข)

    ── ระบบโมดูลเสริม (Optional Modules) ───────────────────────────────
    *** Key ชื่อ Optional_month_rows_X และ Optional_year_rows_X (ไม่มีคำว่า "modules") ***

    "Optional_modules_count"  : จำนวนระบบโมดูลเสริมที่ลูกค้าซื้อเพิ่ม (ตัวเลข)
    "Optional_modules_rows_1" : ชื่อระบบโมดูลเสริมที่ 1
    "Optional_month_rows_1"   : ราคาต่อเดือนของโมดูลที่ 1 ตัวเลขเท่านั้นถ้าเป็น
    "Optional_year_rows_1"    : ราคาต่อปีของโมดูลที่ 1 ตัวเลขเท่านั้น
    "Optional_modules_rows_2" : ชื่อระบบโมดูลเสริมที่ 2
    "Optional_month_rows_2"   : ราคาต่อเดือนของโมดูลที่ 2 ตัวเลขเท่านั้น
    "Optional_year_rows_2"    : ราคาต่อปีของโมดูลที่ 2 ตัวเลขเท่านั้น
    "Optional_modules_rows_3" : ชื่อระบบโมดูลเสริมที่ 3
    "Optional_month_rows_3"   : ราคาต่อเดือนของโมดูลที่ 3 ตัวเลขเท่านั้น
    "Optional_year_rows_3"    : ราคาต่อปีของโมดูลที่ 3 ตัวเลขเท่านั้น

    ── จำนวนผู้ใช้งานและบริษัทในเครือ ──────────────────────────────────

    "User_with_program"               : จำนวนผู้ใช้งานที่มาพร้อมโปรแกรม (Standard Users) ตัวเลขเท่านั้นแต่ถ้าไม่มีให้ใส่ตัวเลข 0 ห้ามเอา Add_concurrent มาใส่เ
    "Free_user_count"                 : จำนวนผู้ใช้งานแบบฟรี (Free Users) **แยกเป็นต้วเลขเท่านั้น** ต้องมีคำว่า Free of charge เท่านั้น
    *** หมายเหตุ: หากเอกสารเขียนรวมกน เช่น "Total 50 Users (Includes 5 Free)" หรือ "Standard 45 + Free 5"
       ให้แยกเป็ฯ User_with_program=45 และ Free_user_count=5 โดยตรง ห้ามส่งค่ารวมกน ***
    "Add_concurrent"                  : จำนวนผู้ใช้งานพร้อมกันแบบซื้อเพิ่ม (Add Concurrent Users)
    "Add_concurrent_rate_price_month" : อัตราค่าบริการรายเดือนของผู้ใช้งานที่ซื้อเพิ่ม ตัวเลขเท่านั้น
    "Add_concurrent_rate_price_year"  : อัตราค่าบริการรายปีของผู้ใช้งานที่ซื้อเพิ่ม ตัวเลขเท่านั้น
    "Add_concurrent_rate_price_after" : อัตราค่าบริการรายเดือนต่อ 1 User หลังรวมกับผู้ใช้มาตรฐานแล้ว ตัวเลขเท่านั้น
    "Multi_company_count"             : จำนวนบริษัทในเครือ (Multi Company) ตัวเลขเท่านั้น
    "Add_multi_rate_price"            : อัตราค่าบริการรายเดือน/รายปีของบริษัทในเครือที่ซื้อเพิ่ม

    ── Applications และ Cloud ────────────────────────────────────────────

    [ถังแอปฟรี — ถ้าเจอชื่อแอปในเอกสารให้ match กับรายการนี้แล้วคัดลอกชื่อมาตรงๆ]
    Free_list: "การอนุมัติเอกสาร (Document Approval)", "การรับของ (PO Received)", "การตรวจนับทรัพย์สิน (Count Asset)", "การแจ้งเตือน (Notification)", "การจัดทำเอกสารเบิก โอน จ่ายวัสดุ (Mango ICM)", "อัปเดตความก้าวหน้าของงาน (Update Progress)", "ระบบตรวจงาน (Mango QCM)"

    [ถังแอปมีค่าใช้จ่าย — ถ้าเจอชื่อแอปในเอกสารให้ match กับรายการนี้แล้วคัดลอกชื่อมาตรงๆ]
    Pay_list: " Realty Quick (ขาย/ออกใบเสนอราคา)","การบันทึกเอกสารเบิกเงินสดย่อย (Mango Petty Cash)", "การบันทึกเอกสารขอซื้อ ขอจ้าง (Mango PR)", "การรับวางบิลผู้รับเหมา (Mango Billing)", "สรุปภาพรวมของทุกโครงการ (Mango PM)"

    "Free_applications_list"    : รายชื่อแอปฟรีที่ลูกค้าได้รับ ให้ดึงจากถัง Free_list ตามที่ปรากฏในเอกสาร ต้องเป็น string คั่นด้วย \n เช่น "การอนุมัติเอกสาร (Document Approval)\nการรับของ (PO Received)"
    "Paid_applications_list"    : รายชื่อแอปมีค่าใช้จ่ายที่ลูกค้าซื้อเพิ่ม ให้ดึงจากถัง Pay_list ตามที่ปรากฏในเอกสาร ต้องเป็น string คั่นด้วย \n
    "Cloud_usage_space_details" : รายละเอียดการใช้งาน Cloud เช่น ขนาดพื้นที่ จำนวนฐานข้อมูล จำนวน User พร้อมกัน การสำรองข้อมูล

    ── การวางระบบ (Implement) ───────────────────────────────────────────

    "Deposit_amount"         : จำนวนเงินมัดจำประกันการใช้โปรแกรม ให้นำราคาจาก item_name "เงินประกันการใช้โปรแกรม" มาใส่ตรงๆ ไม่ต้องคูณหรือหารใดๆ ตัวเลขเท่านั้น เช่น 60000
    "Implement_package_name" : ชื่อแพคเกจการวางระบบ (Implement) ต้องเป็นหนึ่งใน "Start up", "Mini Lite", "Lite", "Silver", "Silver Plus", "Gold", "Platinum" เท่านั้น
    "Implement_price"        : มูลค่าสัญญางานวางระบบ ตัวเลขเท่านั้น
    "Implement_mandays"      : ระยะเวลาการวางระบบ ระบุเป็นจำนวน Man-day
    "Support_rate_per_manday": อัตราค่าบริการสนับสนุน/อบรมเพิ่มเติมต่อครั้ง ตัวเลขเท่านั้น เช่น 14000

    ── งวดการชำระเงิน (Payment Installments) ───────────────────────────
    *** กฎการสร้าง Payment_price_X และ Payment_description_X ***
    1. นับจำนวนงวดจริงในใบเสนอราคา (อาจมี 2, 3 หรือ 4 งวด ไม่บังคับ)
    2. สร้าง field เฉพาะงวดที่มีอยู่จริงเท่านั้น ห้ามสร้าง field งวดที่ไม่มีในเอกสาร
    3. Payment_price_X ใส่ตัวเลขเงินของงวดนั้น ตัวเลขเท่านั้น เช่น 90000
    4. Payment_description_X ให้อ่านเนื้อหาของแต่ละงวด แล้ว match กับถังข้อความกฎหมายที่มีความหมายใกล้เคียงที่สุด
       ห้ามเปลี่ยนแปลงข้อความกฎหมายเด็ดขาด ให้คัดลอกมาตรงๆ

    [ถังข้อความกฎหมาย — match ด้วยเนื้อหา ไม่ใช่ลำดับ]
    เมื่อเนื้อหางวดเกี่ยวกับ: ยืนยัน PO / ยืนยันใบเสนอราคา / ลงนามสัญญา / เริ่มโครงการ / Kick Off
    → "เมื่อผู้รับอนุญาตยืนยันใบสั่งซื้อ (Purchase Order) และ/หรือยืนยันใบเสนอราคา "

    เมื่อเนื้อหางวดเกี่ยวกับ: Master Data / ข้อมูลหลัก / วิเคราะห์ระบบ / Analyze / Conceptual Design
    → "เมื่อผู้อนุญาตดำเนินการจัดทำและนำเข้าข้อมูลหลัก (Master Data) ตามขอบเขตงานที่กำหนดแล้วเสร็จ และได้แจ้งให้ผู้รับอนุญาตทราบ"

    เมื่อเนื้อหางวดเกี่ยวกับ: Training / อบรม / ฝึกอบรม / การใช้งาน
    → "เมื่อผู้อนุญาตดำเนินการฝึกอบรมการใช้งานระบบ (Training) ตามขอบเขตงานที่กำหนดแล้วเสร็จ และได้แจ้งให้ผู้รับอนุญาตทราบ"

    เมื่อเนื้อหางวดเกี่ยวกับ: Go Live / เริ่มใช้งานจริง / ก่อนใช้งาน / งวดสุดท้าย
    → "ภายใน 7 (เจ็ด) วันก่อนวันเริ่มใช้งานระบบจริง (Go Live Date) ตามที่คู่สัญญาตกลงร่วมกัน"

    ตัวอย่าง กรณีมี 2 งวด (งวดที่ 1 = Kick Off, งวดที่ 2 = Training):
    → "Payment_price_1": "300000", "Payment_description_1": "เมื่อผู้รับอนุญาตยืนยันใบสั่งซื้อ (Purchase Order)..."
    → "Payment_price_2": "300000", "Payment_description_2": "เมื่อผู้อนุญาตดำเนินการฝึกอบรมการใช้งานระบบ (Training)..."
    → ไม่มี Payment_price_3, Payment_price_4 เลย

    -- Cloud Usage Space Details ---------------------------------
    "Store_install" : พื้นที่สำหรับติดตั้งโปรแกรม (Install) เช่น "พื้นที่สำหรับติดตั้งโปรแกรม (Program Installation Space) จำนวน 100 กิกะไบต์ (GB)"
    "Store_get_data" : พื้นที่สำหรับจัดเก็บเอกสารและข้อมูลต่างๆ เช่น "พื้นที่สำหรับจัดเก็บเอกสารและข้อมูล (Data Storage Space) จำนวน 500 กิกะไบต์ (GB)"

    -- CUSTOM Program -------------------------------------------
    "Customize_price" : ราคาค่าพัฒนาโปรแกรมเพิ่มเติม (Custom Program) ตัวเลขเท่านั้น เช่น 50000
    
    ── เอกสารแนบท้าย ────────────────────────────────────────────────────

    "Quotation_id"                   : เลขที่ใบเสนอราคาที่อ้างอิงเป็นเอกสารแนบท้าย
    "Quotation_date"                 : วันที่ใบเสนอราคา รูปแบบ "1 มกราคม 2567"
    "Subsidiaries_attachment_status" : ถ้ามีบริษัทในเครือ ให้ใส่ "มี" / ถ้าไม่มีให้ใส่ "ไม่มี"

    ตัวอย่างรูปแบบ JSON ที่ต้องการ:
    {{
        "Contract_id": "123456789",
        "Contract_date": "1 มกราคม 2567",
        "Licensee_company_name": "บริษัท แมงโก้ จำกัด",
        "Licensee_tax_id": "",
        "Optional_modules_rows_1": "ระบบ HR",
        "Optional_month_rows_1": "5,000",
        "Optional_year_rows_1": "60,000",
        "Payment_price_1": "300,000",
        "Payment_description_1": "เมื่อผู้รับอนุญาตยืนยันใบสั่งซื้อ (Purchase Order) และ/หรือยืนยันใบเสนอราคา หรือเมื่อคู่สัญญาลงนามในสัญญา แล้วแต่เหตุการณ์ใดเกิดขึ้นก่อน",
        "Payment_price_2": "300,000",
        "Payment_description_2": "เมื่อผู้อนุญาตดำเนินการฝึกอบรมการใช้งานระบบ (Training) ตามขอบเขตงานที่กำหนดแล้วเสร็จ และได้แจ้งให้ผู้รับอนุญาตทราบ"
    }}
    """

    print("=" * 60)
    print(f"[GEMINI] ===== กำลังส่งข้อมูลให้ Gemini =====")
    print(f"  prompt size : {len(prompt):,} ตัวอักษร")
    print(f"  มี DBD      : {'ใช่' if dbd_profile else 'ไม่มี'}")
    print("=" * 60)

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=[prompt],
        config={
            "response_mime_type": "application/json",
            "temperature": 0.0,
        }
    )
    raw_response = response.text
    usage = response.usage_metadata
    cost_usd = (usage.prompt_token_count * 1.5 + usage.candidates_token_count * 9.0) / 1_000_000
    cost_thb = cost_usd * 35.0
    print("=" * 60)
    print("[GEMINI] ===== ผลลัพธ์จาก Gemini =====")
    print(f"  input tokens : {usage.prompt_token_count:,}")
    print(f"  output tokens: {usage.candidates_token_count:,}")
    print(f"  total tokens : {usage.total_token_count:,}")
    print(f"  ราคา         : ${cost_usd:.6f}  ({cost_thb:.4f} THB)")
    print(f"  response len : {len(raw_response) if raw_response else 0:,} ตัวอักษร")
    print("=" * 60)

    if raw_response is None:
        raise HTTPException(status_code=500, detail="Gemini returned no content.")

    clean_json = extract_json_from_qwen_response(raw_response)
    return clean_json

# =================================================================
# Post-process: คำนวณ field ที่ derive จาก field อื่น
# =================================================================
def post_process(cleaned_data: CleanQuotationData, data: dict) -> dict:

    def to_num(val):
        try:
            return float(str(val).replace(",", "").strip())
        except:
            return 0.0

    def to_baht(val):
        try:
            num = to_num(val)
            if num == 0:
                return "แบบไม่มีค่าใช้จ่าย (free of charge)"
            return bahttext(num).removesuffix("ถ้วน")
        except:
            return ""

    def fmt(val):
        try:
            return f"{to_num(val):,.0f}"
        except:
            return str(val)

    def is_zero(val):
        # เป็นตัวเลขศูนย์จริงๆ เท่านั้น (ไม่นับ "-", ค่าว่าง หรือข้อความอื่นที่ parse ไม่ได้)
        try:
            return float(str(val).replace(",", "").strip()) == 0
        except:
            return False

    # ── คำนวณ License fee เดือน/ปี โดย "บวกยอดทุกรายการที่จ่ายรอบเดียวกัน" ──
    # ราคารายปี/รายเดือนในใบเสนอราคาไม่ได้ระบุแยกไว้ตรงๆ จึงต้องรวมยอด (price = ยอดรวมทั้งบรรทัด)
    # ของทุกรายการที่เป็นรอบเดียวกันเข้าด้วยกัน
    #   • รายปี   = รวม price ของรายการที่เป็นรายปี (unit=year/ปี หรือ qty=12 + unit=month)
    #   • รายเดือน = รวม price ของรายการที่เป็นรายเดือน
    # ยกเว้น: เงินประกันการใช้โปรแกรม และ งานวางระบบ (Implement) เพราะเป็นค่าจ่ายครั้งเดียว ไม่ใช่ค่ารายรอบ
    EXCLUDE_KEYWORDS = ["เงินประกันการใช้โปรแกรม", "วางระบบ", "implement"]

    def is_excluded(name: str) -> bool:
        low = (name or "").lower()
        return any(kw.lower() in low for kw in EXCLUDE_KEYWORDS)

    def is_annual_item(item) -> bool:
        unit = (item.unit or "").strip().lower()
        return "year" in unit or "ปี" in unit or (item.quantity == 12 and "month" in unit)

    year_sum = 0.0
    month_sum = 0.0
    for item in cleaned_data.products_and_services:
        if is_excluded(item.item_name):
            continue
        if is_annual_item(item):
            year_sum += item.price
        else:
            month_sum += item.price

    # โหมดการชำระเงินของใบเสนอราคานี้: เป็นรายปี เมื่อมียอดรายปีและไม่มียอดรายเดือน
    is_year_billing = year_sum > 0 and month_sum == 0

    if year_sum > 0:
        data["License_fee_year_price"] = fmt(year_sum)
        data["License_fee_year_text"]  = to_baht(year_sum)
    else:
        data["License_fee_year_price"] = "-"
        data["License_fee_year_text"]  = ""

    if month_sum > 0:
        data["License_fee_month_price"] = fmt(month_sum)
        data["License_fee_month_text"]  = to_baht(month_sum)
    else:
        data["License_fee_month_price"] = "-"
        data["License_fee_month_text"]  = ""

    # ── เงินประกัน: มีเฉพาะแบบรายเดือน ── ถ้าเป็นรายปีไม่มีเงินประกัน ให้เคลียร์ทิ้ง ──
    if is_year_billing:
        data["Deposit_amount"]      = ""
        data["Deposit_amount_text"] = ""
    else:
        data["Deposit_amount_text"] = to_baht(data.get("Deposit_amount", 0))

    # ── แปลงตัวหนังสือราคาอื่นๆ ──────────────────────
    data["Implement_price_text"]         = to_baht(data.get("Implement_price", 0))
    data["Support_rate_per_manday_text"] = to_baht(data.get("Support_rate_per_manday", 0))
    data["Customize_price_text"]         = to_baht(data.get("Customize_price", 0))

    # ── Optional Modules text ──────────────────────────
    for i in range(1, 4):
        m_key = f"Optional_month_rows_{i}"
        y_key = f"Optional_year_rows_{i}"
        if data.get(m_key) and data[m_key] != "-":
            data[f"Text_month_row_{i}"] = to_baht(data[m_key])
        if data.get(y_key) and data[y_key] != "-":
            y_text = to_baht(data[y_key])
            # ถ้าเป็น free of charge ไม่ต้องครอบวงเล็บซ้ำ (ในข้อความมีวงเล็บอยู่แล้ว)
            data[f"Text_year_row_{i}"]  = y_text if is_zero(data[y_key]) else f"({y_text})"

    # ── Add concurrent text ────────────────────────────
    if data.get("Add_concurrent_rate_price_after"):
        data["Add_concurrent_rate_price_text_after"] = to_baht(
            data["Add_concurrent_rate_price_after"]
        )

    # ── ราคาที่เป็น 0 (free of charge) ไม่ต้องแสดงเลข 0 ในเอกสาร ──
    # เคลียร์ฝั่งตัวเลขให้ว่าง เหลือแค่คำอ่าน "แบบไม่มีค่าใช้จ่าย (free of charge)"
    zero_price_keys = [
        "License_fee_month_price", "License_fee_year_price",
        "Deposit_amount", "Implement_price", "Support_rate_per_manday",
        "Add_concurrent_rate_price_after",
        *[f"Optional_month_rows_{i}" for i in range(1, 4)],
        *[f"Optional_year_rows_{i}" for i in range(1, 4)],
    ]
    for key in zero_price_keys:
        if is_zero(data.get(key)):
            data[key] = ""

    return data

# =================================================================
# Helper: บันทึก final_data ลง eval/predictions/<quotation_id>.json
# เพื่อใช้เทียบกับ eval/ground_truth/ ทีหลัง (dev accuracy tool)
# =================================================================
EVAL_PREDICTIONS_DIR = Path(__file__).resolve().parent / "eval" / "predictions"

def save_eval_prediction(quotation_id: str, data: dict) -> None:
    try:
        EVAL_PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = EVAL_PREDICTIONS_DIR / f"{quotation_id}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[DEBUG] บันทึก eval prediction ไปที่ {path}")
    except Exception as e:
        print(f"[WARN] บันทึก eval prediction ไม่สำเร็จ: {e}")

# =================================================================
# Helper: แปลงข้อมูลเป็น RichText สีแดง ขีดเส้นใต้
# =================================================================
def wrap_values_richtext(data):
    if isinstance(data, dict):
        return {k: wrap_values_richtext(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [wrap_values_richtext(item) for item in data]
    elif isinstance(data, str) and data.strip():
        rt = RichText()
        rt.add(data.strip(' \t\n\r\'",' ), color='FF0000', underline=True, font='TH SarabunPSK', size=28)
        return rt
    elif data is not None:
        rt = RichText()
        rt.add(str(data).strip(' \t\n\r\'",'), color='FF0000', underline=True, font='TH SarabunPSK', size=28)
        return rt
    return data

# =================================================================
# FastAPI Application Setup
# =================================================================
app = FastAPI(title="Mango Contract Generation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/login")
async def login(credentials: LoginRequest):
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] พยายามล็อกอิน: userid={credentials.userid}")
        response = http_requests.post(
            EXTERNAL_AUTH_LOGIN_URL,
            json={
                "maincode": MAINCODE,
                "userid": credentials.userid,
                "userpass": credentials.userpass,
            },
            timeout=300,
        )
        if response.status_code == 200:
            result = response.json()
            success = result.get("success", False) if isinstance(result, dict) else bool(result)
            if success:
                print(f"[✅ สำเร็จ] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] userid={credentials.userid}")
            else:
                error_msg = result.get("error", "ไม่ทราบสาเหตุ") if isinstance(result, dict) else ""
                print(f"[❌ ล้มเหลว] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] userid={credentials.userid} | error={error_msg}")
            return result
        else:
            try:
                detail = response.json().get("detail", "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
            except Exception:
                detail = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
            raise HTTPException(status_code=response.status_code, detail=detail)
    except http_requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="ไม่สามารถเชื่อมต่อกับระบบยืนยันตัวตนภายนอกได้ กรุณาลองใหม่อีกครั้ง")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการล็อกอิน: {str(e)}")

async def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบก่อนใช้งาน")
    token = authorization.split("Bearer ", 1)[1]
    try:
        response = http_requests.get(
            EXTERNAL_QUOTATION_URL,
            headers={"X-Mango-Auth": token},
            timeout=150,
        )
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=401, detail="Token หมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="ไม่สามารถตรวจสอบสิทธิ์การใช้งานได้")

@app.get("/quotation/{quotation_id}")
async def get_quotation(quotation_id: str, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบก่อนใช้งาน")
    token = authorization.split("Bearer ", 1)[1]
    try:
        response_quotation = http_requests.get(
            EXTERNAL_QUOTATION_URL,
            params={"docno": quotation_id},
            headers={"X-Mango-Auth": token},
            timeout=300,
        )
        if response_quotation.status_code == 200:
            return response_quotation.json()
        else:
            raise HTTPException(status_code=response_quotation.status_code, detail="ไม่สามารถดึงข้อมูลใบเสนอราคาได้")
    except HTTPException:
        raise
    except http_requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="ไม่สามารถเชื่อมต่อกับระบบภายนอกได้")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการดึงข้อมูล: {str(e)}")

@app.post("/parse-dbd")
async def parse_dbd_endpoint(
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบก่อนใช้งาน")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ PDF เท่านั้น")
    try:
        file_bytes = await file.read()
        extracted = parse_dbd_pdf(file_bytes)
        return JSONResponse(content={"dbd_data": extracted, "fields_found": list(extracted.keys())})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ไม่สามารถอ่านไฟล์ DBD ได้: {str(e)}")

@app.post("/generate-contract")
async def generate_contract(
    payload: quotation,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    authorization: str = Header(None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบก่อนใช้งาน")

    try:
        parsed_json = payload.result_quotation
        quotation_id = payload.quotation_id

        print("=" * 60)
        print(f"[CONTRACT] ===== เริ่มสร้างสัญญา: {quotation_id} =====")
        print(f"  มี DBD: {'ใช่ — ' + str(payload.dbd_data.get('company_name')) if payload.dbd_data else 'ไม่มี'}")
        print("=" * 60)

        # 1. ทำความสะอาดข้อมูล
        cleaned_data = filter_and_clean_quotation(parsed_json)
        print(f"[1/5] CLEAN — customer={cleaned_data.customer_name} | items={len(cleaned_data.products_and_services)} | payments={len(cleaned_data.payment_terms)}")

        # 2. ส่งให้ Gemini สกัดข้อมูล (รวม DBD profile ถ้ามี)
        gemini_analysis = analyze_with_gemini(cleaned_data, dbd_profile=payload.dbd_data)

        # 3. Parse JSON — ไม่ validate ผ่าน Pydantic เพราะ Key เป็น dynamic
        try:
            final_data = try_parse_json(gemini_analysis)
            print(f"[3/5] PARSE — keys ทั้งหมด ({len(final_data)}): {list(final_data.keys())}")
            print(f"  Licensee_company_name    : {final_data.get('Licensee_company_name')}")
            print(f"  Licensee_tax_id          : {final_data.get('Licensee_tax_id')}")
            print(f"  Licensee_authorized_person: {final_data.get('Licensee_authorized_person')}")
            print(f"  Licensee_address         : {final_data.get('Licensee_address')}")
            print(f"  Deposit_amount           : {final_data.get('Deposit_amount')}")
            print(f"  Contract_date            : {final_data.get('Contract_date')}")
        except Exception as e:
            print(f"[❌ JSON Error] {str(e)}")
            raise HTTPException(status_code=500, detail=f"ข้อมูลจาก AI ไม่ถูกต้อง: {str(e)}")

        # 4. คำนวณ field ที่ derive (License fee, text versions ฯลฯ)
        final_data = post_process(cleaned_data, final_data)
        print(f"[4/5] POST-PROCESS — License_fee_month={final_data.get('License_fee_month_price')} | License_fee_year={final_data.get('License_fee_year_price')}")

        # 5. Wrap เป็น RichText สีแดง ขีดเส้นใต้
        wrapped_data = wrap_values_richtext(final_data)

        # 5.5 Flag ธรรมดา (ไม่ใช่ RichText) บอก template ว่า field นี้เป็น "-" หรือไม่
        #     ใช้เพื่อซ่อนวงเล็บ "( )" ของ Text_month_row_X / Text_year_row_X เมื่อไม่ได้ถูกเลือก
        for i in range(1, 4):
            for prefix in ("Optional_month_rows_", "Optional_year_rows_"):
                key = f"{prefix}{i}"
                wrapped_data[f"{key}_is_dash"] = str(final_data.get(key, "")).strip() == "-"


        # 6. Render template
        doc = DocxTemplate('TEMPLA~1 - Copy.docx')
        doc.render(wrapped_data)

        # 7. บันทึกลง BytesIO (ไม่ใช้ disk)
        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        file_bytes = doc_io.read()

        print("=" * 60)
        print(f"[5/5] DONE — สร้างไฟล์ {quotation_id}.docx สำเร็จ ({len(file_bytes):,} bytes)")
        print("=" * 60)
        

        
        return JSONResponse(content={
            "file_base64": base64.b64encode(file_bytes).decode("ascii"),
            "file_name": f"สัญญา_{quotation_id}.docx",
            "contract_data": final_data,
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในระบบ: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการประมวลผลเอกสาร: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "back_end:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_excludes=["eval/*", "temp_files/*"],
    )