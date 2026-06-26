import io
import os
import json
import base64
from datetime import datetime
import requests as http_requests
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
from openai import OpenAI
from pydantic import BaseModel, Field
import sys
import uuid
import shutil
from dotenv import load_dotenv
from copy import deepcopy
from docxtpl import DocxTemplate, RichText


from docx.oxml import OxmlElement
from pydantic import BaseModel
from typing import List, Optional
import ast
import re

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Depends, Header
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# บังคับใช้ UTF-8 สำหรับการแสดงผลบน Terminal
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

# ตั้งค่าโมเดล Qwen
QWEN_API_KEY = os.environ.get("QWEN_API_KEY")
QWEN_API_BASE_URL = os.environ.get("QWEN_API_BASE_URL")
client = OpenAI(
    base_url=QWEN_API_BASE_URL,
    api_key=QWEN_API_KEY
)
print(f"[DEBUG] QWEN_API_KEY loaded: {bool(QWEN_API_KEY)}")
print(f"[DEBUG] QWEN_API_BASE_URL: {QWEN_API_BASE_URL}")


# =================================================================
# การตั้งค่า External Authentication API
# =================================================================
# URL สำหรับล็อกอิน (ส่ง username/password ไปเพื่อรับ Token กลับมา)
EXTERNAL_AUTH_LOGIN_URL = os.environ.get(
    "EXTERNAL_AUTH_LOGIN_URL",
    "https://demotokbud.mangoanywhere.com/production.service/api/public/login"  # <-- เปลี่ยนเป็น URL จริงของท่าน
)
# URL สำหรับตรวจสอบ Token (ส่ง Token ไปเพื่อดูว่ายังใช้ได้อยู่หรือไม่)
EXTERNAL_AUTH_VERIFY_URL = os.environ.get(
    "EXTERNAL_AUTH_VERIFY_URL",
    "https://demotokbud.mangoanywhere.com/production.service/Anywhere/BD/QO_ReadData?docno=QO2603TRA001"  # <-- เปลี่ยนเป็น URL จริงของท่าน
)

# รหัสบริษัทที่ใช้ล็อกอิน (ตั้งค่าคงที่ไว้ที่หลังบ้าน ไม่ต้องกรอกจากหน้าเว็บ)
MAINCODE = os.environ.get("MAINCODE", "MANGO")  # <-- เปลี่ยนเป็นรหัสบริษัทจริงของท่าน

# URL สำหรับดึงข้อมูลใบเสนอราคา (QO_ReadData)
EXTERNAL_QUOTATION_URL = os.environ.get(
    "EXTERNAL_QUOTATION_URL",
    "https://demotokbud.mangoanywhere.com/production.service/Anywhere/BD/QO_ReadData"
)

class LoginRequest(BaseModel):
    userid: str
    userpass: str

class quotation(BaseModel):
    quotation_id: str
    result_quotation: dict
    
    
class CleanItem(BaseModel):
    item_name: str
    quantity: float
    unit: str
    price: float  # เลือกระหว่าง net_amount หรือ sell_amount
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
    terms_and_conditions: str  # รวมข้อความเงื่อนไขทั้งหมดไว้ให้ AI อ่านง่ายๆ
    
    
    
# =================================================================
# Schema สำหรับ Structured Output
# =================================================================
class TableItem(BaseModel): 
    specification: str = Field(description="รายละเอียดสินค้า รายละเอียดบริการ หรือข้อกำหนด/รายการในตาราง")
    total_amount: str = Field(description="ราคารวม จำนวนเงิน หรือมูลค่าประจำรายการนั้น")


class ContractResponse(BaseModel):
    Contract_id: str = Field(description="สัญญาเลขที่")
    Contract_date: str = Field(description="วันที่ทำสัญญา")
    Customer_company_name: str = Field(description="ชื่อบริษัทลูกค้า (ผู้รับอนุญาต)")
    Customer_tax_id: str = Field(description="เลขทะเบียนนิติบุคคลของบริษัทลูกค้า")
    Customer_director_name: str = Field(description="ชื่อกรรมการบริษัท หรือผู้รับมอบอำนาจของบริษัทลูกค้า")
    Customer_address: str = Field(description="ที่ตั้งสำนักงานของบริษัทลูกค้า")
    Standard_module_count: str = Field(description="จำนวน Module มาตรฐานที่ได้รับสิทธิ")
    Standard_module_name: str = Field(description="ชื่อแพ็กเกจหรือประเภทสำหรับ Module มาตรฐาน")
    Standard_users_count: str = Field(description="จำนวนผู้ใช้งานเบื้องต้นสำหรับระบบมาตรฐาน")

    License_fee: str = Field(description="จำนวนเงินค่าสิทธิการใช้โปรแกรม (License fee) รายเดือน ระบุทั้งตัวเลขและตัวหนังสือ")
    License_fee_month: str = Field(description="ค่าสิทธิการใช้โปรแกรม (License fee) รายเดือน ระบุเป็นตัวเลข")
    License_fee_year: str = Field(description="ค่าสิทธิการใช้โปรแกรม (License fee) รายปี ระบุทั้งตัวเลขและตัวหนังสือ")
    Cloud_usage_description: str = Field(description="รายละเอียดการใช้งานระบบ Cloud")
    Concurrent_users: str = Field(description="จำนวนผู้ใช้งานพร้อมกัน (Concurrent Users) ที่รวมมากับโปรแกรม")
    Additional_concurrent_users: str = Field(description="จำนวนผู้ใช้งานพร้อมกันแบบซื้อเพิ่มเติม")
    Add_concurrent_rate_price: str = Field(description="ราคาค่าบริการ Add Concurrent Users ระบุทั้งตัวเลขและตัวหนังสือ")
    Add_multi_company_count: str = Field(description="จำนวนบริษัทในเครือ (Add Multi Company)")
    Add_multi_rate_price: str = Field(description="ราคาค่าบริการ Add Multi Company ระบุทั้งตัวเลขและตัวหนังสือ")
    Optional_module_count: str = Field(description="จำนวนระบบโมดูลเสริม (Optional Modules) ที่เลือกใช้งานเพิ่มเติม")
    Optional_module_details: str = Field(description="รายชื่อระบบโมดูลเสริม พร้อมระบุราคาต่อเดือนเป็นตัวเลขและตัวหนังสือ")
    Implement_package_name: str = Field(description="ชื่อแพคเกจสำหรับการวางระบบซอฟต์แวร์ (Implement)")
    Implement_price: str = Field(description="มูลค่าสัญญางานวางระบบ ระบุทั้งตัวเลขและตัวหนังสือ")
    Implement_mandays: str = Field(description="จำนวนวันทำงาน (Man-day) สำหรับการวางระบบซอฟต์แวร์ (Implement)")
    Implement_payment_terms: str = Field(description="เงื่อนไขและงวดการชำระเงินสำหรับค่าวางระบบ โดยต้องระบุคำว่า 'ชำระ' ต่อท้าย 'งวดที่ X' เสมอ เช่น 'งวดที่ 1 ชำระ 30%...'")
    Deposit_amount: str = Field(description="จำนวนเงินมัดจำประกันการใช้โปรแกรมล่วงหน้า 2 เดือน ระบุทั้งตัวเลขและตัวหนังสือ")
    Customize_man_days: str = Field(description="จำนวนวันทำงาน (Man-day) สำหรับการพัฒนาโปรแกรมเพิ่มเติม")
    Customize_rate_per_day: str = Field(description="อัตราค่าบริการพัฒนาโปรแกรมเพิ่มเติมต่อ 1 วันทำงาน ระบุทั้งตัวเลขและตัวหนังสือ")
    Support_rate_per_manday: str = Field(description="อัตราค่าบริการ Support ต่อ 1 วันทำงาน (Man-day) ระบุเป็นตัวเลข")
    Support_rate_per_manday_text: str = Field(description="อัตราค่าบริการ Support ต่อ 1 วันทำงาน (Man-day) ระบุเป็นตัวหนังสือ")
    Mandays_count: str = Field(description="จำนวนวันทำงาน (Man-day) สำหรับการวางระบบซอฟต์แวร์ (Implement)")
    Manday_price: str = Field(description="ราคาต่อวันสำหรับการวางระบบซอฟต์แวร์ (Implement)")
    Quotation_id: str = Field(description="เลขที่ใบเสนอราคาที่นำมาอ้างอิงเป็นเอกสารแนบท้าย")
    Quotation_date: str = Field(description="วันที่ของใบเสนอราคา")
    Customer_company_signature_name: str = Field(description="ชื่อบริษัทลูกค้าสำหรับประทับตราในหน้าลงนาม")
    Customer_authorized_signature: str = Field(description="ลายมือชื่อและชื่อตัวบรรจงของผู้มีอำนาจลงนามฝ่ายลูกค้า")
    Customer_position: str = Field(description="ตำแหน่งของผู้มีอำนาจลงนามฝ่ายลูกค้า")
    Customer_email: str = Field(description="อีเมลของผู้มีอำนาจลงนามฝ่ายลูกค้า")
    Customer_witness_signature: str = Field(description="ลายมือชื่อพยานฝ่ายลูกค้า")
    Customer_witness_email: str = Field(description="อีเมลของพยานฝ่ายลูกค้า")

# =================================================================
# Helper: แยก JSON จาก Qwen response (อาจมี markdown code blocks)
# =================================================================
def extract_json_from_qwen_response(response_text: str) -> str:
    """
    แยก JSON จาก Qwen response ที่อาจมีมาร์กดาวน์ code blocks หรือข้อความล้อมรอบ
    """
    import re
    print(f"[DEBUG] extract_json_from_qwen_response start, raw len={len(response_text)}")

    # Try 1: Extract from markdown JSON code block
    if '```json' in response_text:
        parts = response_text.split('```json', 1)[1].split('```', 1)
        if parts:
            result = parts[0].strip()
            print(f"[DEBUG] extracted from ```json block, len={len(result)}")
            return result

    # Try 2: Extract from generic markdown code block
    if '```' in response_text:
        parts = response_text.split('```', 2)
        if len(parts) >= 3:
            candidate = parts[1].strip()
            if candidate.lower().startswith('json'):
                candidate = candidate.split('\n', 1)[1].strip() if '\n' in candidate else candidate
            print(f"[DEBUG] extracted from generic ``` block, len={len(candidate)}")
            return candidate

    # Try 3: Extract the first balanced JSON object from text
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
                    result = response_text[start:idx+1].strip()
                    print(f"[DEBUG] extracted balanced JSON object, len={len(result)}")
                    return result

    # Fallback: trim whitespace
    result = response_text.strip()
    print(f"[DEBUG] fallback return stripped response, len={len(result)}")
    return result


# Robust JSON parsing: try json.loads, ast.literal_eval, and simple fallbacks
def try_parse_json(text: str):
    text = (text or '').strip()
    import json
    if not text:
        raise json.JSONDecodeError("Empty response", text, 0)

    # 1) Standard JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) Python literal (single quotes) via ast
    try:
        obj = ast.literal_eval(text)
        # ast.literal_eval can return non-dict/list (e.g., a string) — keep as-is
        return obj
    except Exception:
        pass

    # 3) Heuristic: replace single quotes with double quotes when there are no double quotes
    try:
        s = text
        if '"' not in s and "'" in s:
            s = s.replace("'", '"')
        # remove trailing commas before } or ]
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
    detail2 = data.get("detail2", []) # รายการสินค้า/บริการ
    detail3 = data.get("detail3", []) # พวกเงื่อนไขและหมายเหตุยาวๆ
    detail4 = data.get("detail4", []) # งวดการชำระเงิน

    # 2.1 รวมที่อยู่ลูกค้า
    address_parts = [
        header.get("address1", ""),
        header.get("address2", ""),
        header.get("address3", "")
    ]
    full_address = " ".join([p for p in address_parts if p]).strip()
    
    amount = header.get("amount", 0.0)
    discount = header.get("total_discount", 0.0)
    vat = header.get("vat_amount", 0.0)
    
    # 2.2 กรองรายการสินค้า/บริการ (เอาเฉพาะฟิลด์ที่จำเป็น)
    clean_items = []
    for item in details:
        name = item.get("type_name")
        if name:
            # บางรายการ net_amount เป็น 0 แต่มี sell_amount เราจึงใช้ดักไว้
            price = item.get("sell_amount") or 0.0
            clean_items.append(CleanItem(
                item_name=name.strip(),
                quantity=item.get("qty", 0.0),
                unit=item.get("unitname", ""),
                price=price,
                remark=item.get("mat_other")
            ))

    # 2.3 กรองงวดการชำระเงิน
    clean_payment_terms = []
    for term in detail4:
        clean_payment_terms.append(CleanPaymentTerm(
            period=term.get("desc_period", ""),
            description=term.get("description", ""),
            amount=term.get("amt", 0.0)
        ))

    # 2.4 รวม Text เงื่อนไขทั้งหมดจาก detail3 เป็นก้อนเดียวให้ AI อ่านเพื่อดึงค่า
    # เช่น ค่า Man-day 14,000, ค่า Customize 20,000 จะซ่อนอยู่ในนี้
    tnc_lines = [d.get("remark", "") for d in detail3 if d.get("remark")]
    full_tnc_text = "\n".join(tnc_lines)

    # 2.5 ประกอบร่างข้อมูลใหม่
    cleaned_data = CleanQuotationData(
        quotation_id=header.get("docno", ""),
        quotation_date=header.get("docdate", ""),
        customer_name=header.get("customer_name", ""),
        customer_address=full_address,
        total_amount=amount - discount + vat,
        products_and_services=clean_items,
        payment_terms=clean_payment_terms,
        terms_and_conditions=full_tnc_text
    )
    
    return cleaned_data

# =================================================================
# 3. ฟังก์ชันสกัดข้อมูลจากเอกสารด้วย Qwen
# =================================================================
def analyze_with_qwen(parsed_json):
    if isinstance(parsed_json, BaseModel):
        # Pydantic v2: avoid using BaseModel.json(...) with dumps kwargs
        # which may raise "dumps_kwargs keyword arguments are no longer supported".
        try:
            model_data = parsed_json.model_dump()
        except Exception:
            # Fallback: convert via the public json() then load back to dict
            try:
                model_data = json.loads(parsed_json.json())
            except Exception:
                model_data = {}
        document_content = json.dumps(model_data, ensure_ascii=False, indent=2)
    else:
        document_content = json.dumps(parsed_json, ensure_ascii=False, indent=2)
    
    prompt = f"""
    นี่คือข้อมูลใบเสนอราคาจากระบบ (JSON Format):
    {document_content}

    หน้าที่ของคุณคือ สกัดข้อมูลจากใบเสนอราคานี้ตามหัวข้อที่กำหนด และต้องตอบกลับมาในรูปแบบ JSON เท่านั้น

    [กฎข้อบังคับที่ต้องทำตามอย่างเคร่งครัด]
    1. ห้ามมีข้อความเกริ่นนำ ข้อความสรุป หรือคำอธิบายใดๆ ทั้งสิ้น ให้ตอบกลับมาแค่โครงสร้างปีกกา {{...}} ของ JSON เท่านั้น
    2. หากหัวข้อไหนไม่พบข้อมูลในเอกสาร ให้ใส่ค่าเป็น string "ไม่พบข้อมูล" เท่านั้น ห้ามใส่ค่าว่าง "", ห้ามใส่ null, ห้ามข้ามฟิลด์นั้น
    3. ใช้ชื่อ Key ตามที่ระบุด้านล่างนี้เป๊ะๆ ห้ามเปลี่ยนชื่อ Key โดยเด็ดขาด
    4. ห้ามแต่งเติมข้อมูลที่ไม่มีในเอกสารเด็ดขาด
    5. "unit" และ "quantity" ต้องพิจารณาร่วมกัน: ถ้า quantity=12 และ unit=เดือน ให้คิดว่าเป็น 1 ปี
    6. Field ราคา "รายเดือน" vs "รายปี" ให้ใส่ "-" (ขีด) เมื่อรูปแบบการชำระนั้นไม่ได้ถูกเลือก เช่น
       - ถ้าลูกค้าซื้อแบบ "รายปี"   → field _month_price / _month_text / _month_rows_X ทั้งหมดให้ใส่ "-"
       - ถ้าลูกค้าซื้อแบบ "รายเดือน" → field _year_price / _year_text / _year_rows_X ทั้งหมดให้ใส่ "-"
       - กฎนี้ใช้กับทุก field ที่มีคำว่า month หรือ year ใน Key ยกเว้น Contract_date และ Quotation_date
    7. ตัวเลขราคาหรือจำนวนเงินทั้งหมด ต้องใส่เครื่องหมายจุลภาค (,) คั่นหลักพัน (เช่น 10,000)
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
    "License_fee_month_price"      : ค่า License fee รายเดือน ให้นำค่าจาก "Deposit_amount" หาร 2 ตัวเลขเท่านั้น เช่น 30000
    "License_fee_month_text"       : ค่า License fee รายเดือน ให้แปลงจาก "License_fee_month_price" เป็นตัวหนังสือภาษาไทย เช่น "สามหมื่นบาทถ้วน"
    "License_fee_year_price"       : ค่า License fee รายปี ให้นำ "License_fee_month_price" คูณ 12 ตัวเลขเท่านั้น เช่น 360000
    "License_fee_year_text"        : ค่า License fee รายปี ให้แปลงจาก "License_fee_year_price" เป็นตัวหนังสือภาษาไทย เช่น "สามแสนหกหมื่นบาทถ้วน"

    ── ระบบโมดูลเสริม (Optional Modules) ───────────────────────────────
    *** หมายเหตุ: Key ชื่อ Optional_month_rows_X และ Optional_year_rows_X (ไม่มีคำว่า "modules") ***
    *** Text_year_row_X ให้ใส่วงเล็บครอบทุกครั้ง เช่น (หกหมื่นบาทถ้วน) ***

    "Optional_modules_count"  : จำนวนระบบโมดูลเสริมที่ลูกค้าซื้อเพิ่ม (ตัวเลข)
    "Optional_modules_rows_1" : ชื่อระบบโมดูลเสริมที่ 1
    "Optional_month_rows_1"   : ราคาต่อเดือนของโมดูลที่ 1 ตัวเลขเท่านั้น
    "Text_month_row_1"        : ราคาต่อเดือนของโมดูลที่ 1 แปลงเป็นตัวหนังสือภาษาไทย เช่น "ห้าพันบาทถ้วน"
    "Optional_year_rows_1"    : ราคาต่อปีของโมดูลที่ 1 ตัวเลขเท่านั้น
    "Text_year_row_1"         : ราคาต่อปีของโมดูลที่ 1 แปลงเป็นตัวหนังสือภาษาไทย ใส่วงเล็บด้วย เช่น "(หกหมื่นบาทถ้วน)"
    "Optional_modules_rows_2" : ชื่อระบบโมดูลเสริมที่ 2
    "Optional_month_rows_2"   : ราคาต่อเดือนของโมดูลที่ 2 ตัวเลขเท่านั้น
    "Text_month_row_2"        : ราคาต่อเดือนของโมดูลที่ 2 แปลงเป็นตัวหนังสือภาษาไทย เช่น "ห้าพันบาทถ้วน"
    "Optional_year_rows_2"    : ราคาต่อปีของโมดูลที่ 2 ตัวเลขเท่านั้น
    "Text_year_row_2"         : ราคาต่อปีของโมดูลที่ 2 แปลงเป็นตัวหนังสือภาษาไทย ใส่วงเล็บด้วย เช่น "(หกหมื่นบาทถ้วน)"
    "Optional_modules_rows_3" : ชื่อระบบโมดูลเสริมที่ 3
    "Optional_month_rows_3"   : ราคาต่อเดือนของโมดูลที่ 3 ตัวเลขเท่านั้น
    "Text_month_row_3"        : ราคาต่อเดือนของโมดูลที่ 3 แปลงเป็นตัวหนังสือภาษาไทย เช่น "ห้าพันบาทถ้วน"
    "Optional_year_rows_3"    : ราคาต่อปีของโมดูลที่ 3 ตัวเลขเท่านั้น
    "Text_year_row_3"         : ราคาต่อปีของโมดูลที่ 3 แปลงเป็นตัวหนังสือภาษาไทย ใส่วงเล็บด้วย เช่น "(หกหมื่นบาทถ้วน)"

    ── จำนวนผู้ใช้งานและบริษัทในเครือ ──────────────────────────────────

    "User_with_program"                    : จำนวนผู้ใช้งานที่มาพร้อมโปรแกรม (Standard Users) ตัวเลขเท่านั้น
    "Free_user_count"                      : จำนวนผู้ใช้งานแบบไม่เสียค่าใช้จ่าย (Free Users) ต้องมีคำว่า Free of charge
    "Add_concurrent"                       : จำนวนผู้ใช้งานพร้อมกันแบบซื้อเพิ่ม (Add Concurrent Users)
    "Add_concurrent_rate_price_month"      : อัตราค่าบริการรายเดือนของผู้ใช้งานที่ซื้อเพิ่ม ตัวเลขเท่านั้น
    "Add_concurrent_rate_price_year"       : อัตราค่าบริการรายปีของผู้ใช้งานที่ซื้อเพิ่ม ตัวเลขเท่านั้น
    "Add_concurrent_rate_price_after"      : อัตราค่าบริการรายเดือนต่อ 1 User หลังรวมกับผู้ใช้มาตรฐานแล้ว ตัวเลขเท่านั้น
    "Add_concurrent_rate_price_text_after" : อัตราค่าบริการรายเดือนต่อ 1 User หลังรวมกับผู้ใช้มาตรฐานแล้ว ตัวหนังสือ
    "Multi_company_count"                  : จำนวนบริษัทในเครือ (Multi Company) ตัวเลขเท่านั้น
    "Add_multi_rate_price"                 : อัตราค่าบริการรายเดือน/รายปีของบริษัทในเครือที่ซื้อเพิ่ม

    ── Applications และ Cloud ────────────────────────────────────────────

    [ถังแอปฟรี — ถ้าเจอชื่อแอปในเอกสารให้ match กับรายการนี้แล้วคัดลอกชื่อมาตรงๆ]
    Free_list: "การอนุมัติเอกสาร (Document Approval)", "การรับของ (PO Received)", "การตรวจนับทรัพย์สิน (Count Asset)", "การแจ้งเตือน (Notification)", "การจัดทำเอกสารเบิก โอน จ่ายวัสดุ (Mango ICM)", "อัปเดตความก้าวหน้าของงาน (Update Progress)", "ระบบตรวจงาน (Mango QCM)"

    [ถังแอปมีค่าใช้จ่าย — ถ้าเจอชื่อแอปในเอกสารให้ match กับรายการนี้แล้วคัดลอกชื่อมาตรงๆ]
    Pay_list: "การบันทึกเอกสารเบิกเงินสดย่อย (Mango Petty Cash)", "การบันทึกเอกสารขอซื้อ ขอจ้าง (Mango PR)", "การรับวางบิลผู้รับเหมา (Mango Billing)", "สรุปภาพรวมของทุกโครงการ (Mango PM)"

    "Free_applications_list"    : รายชื่อแอปฟรีที่ลูกค้าได้รับ ให้ดึงจากถัง Free_list ตามที่ปรากฏในเอกสาร ต้องเป็น string คั่นแต่ละรายการด้วย \n เช่น "การอนุมัติเอกสาร (Document Approval)\nการรับของ (PO Received)"
    "Paid_applications_list"    : รายชื่อแอปมีค่าใช้จ่ายที่ลูกค้าซื้อเพิ่ม ให้ดึงจากถัง Pay_list ตามที่ปรากฏในเอกสาร ต้องเป็น string คั่นแต่ละรายการด้วย \n เช่น "การบันทึกเอกสารเบิกเงินสดย่อย (Mango Petty Cash)\nการบันทึกเอกสารขอซื้อ ขอจ้าง (Mango PR)"
    "Cloud_usage_space_details" : รายละเอียดการใช้งาน Cloud เช่น ขนาดพื้นที่ จำนวนฐานข้อมูล จำนวน User พร้อมกัน การสำรองข้อมูล

    ── การวางระบบ (Implement) ───────────────────────────────────────────

    "Deposit_amount"          : จำนวนเงินมัดจำประกันการใช้โปรแกรม ให้นำราคาจาก item_name "เงินประกันการใช้โปรแกรม" มาใส่ตรงๆ ไม่ต้องคูณหรือหารใดๆ ระบุตัวเลขเท่านั้น เช่น 60000
    "Deposit_amount_text"     : จำนวนเงินมัดจำประกัน ตัวหนังสือ เช่น "หกหมื่นบาทถ้วน"
    "Implement_package_name"  : ชื่อแพคเกจการวางระบบ (Implement) ต้องเป็นหนึ่งใน "Start up", "Mini Lite", "Lite", "Silver", "Silver Plus", "Gold", "Platinum" เท่านั้น
    "Implement_price"         : มูลค่าสัญญางานวางระบบ ตัวเลขเท่านั้น
    "Implement_price_text"    : มูลค่าสัญญางานวางระบบ ตัวหนังสือ
    "Implement_mandays"       : ระยะเวลาการวางระบบ ระบุเป็นจำนวน Man-day
    "Support_rate_per_manday" : อัตราค่าบริการสนับสนุน/อบรมเพิ่มเติมต่อครั้ง ตัวเลขเท่านั้น เช่น 14000
    "Support_rate_per_manday_text" : อัตราค่าบริการสนับสนุน/อบรมเพิ่มเติมต่อครั้ง ตัวหนังสือ เช่น "หนึ่งหมื่นสี่พันบาทถ้วน"

    ── งวดการชำระเงิน (Payment Installments) ───────────────────────────
    *** กฎการสร้าง Payment_price_X และ Payment_description_X ***
    1. นับจำนวนงวดจริงในใบเสนอราคา (อาจมี 2, 3 หรือ 4 งวด ไม่บังคับ)
    2. สร้าง field เฉพาะงวดที่มีอยู่จริงเท่านั้น ห้ามสร้าง field งวดที่ไม่มีในเอกสาร
    3. Payment_price_X ใส่ตัวเลขเงินของงวดนั้น ตัวเลขเท่านั้น เช่น 90000
    4. Payment_description_X ให้อ่านเนื้อหาของแต่ละงวด แล้ว match กับถังข้อความกฎหมายที่มีความหมายใกล้เคียงที่สุด
       ห้ามเปลี่ยนแปลงข้อความกฎหมายเด็ดขาด ให้คัดลอกมาตรงๆ

    [ถังข้อความกฎหมาย — match ด้วยเนื้อหา ไม่ใช่ลำดับ]
    เมื่อเนื้อหางวดเกี่ยวกับ: ยืนยัน PO / ยืนยันใบเสนอราคา / ลงนามสัญญา / เริ่มโครงการ / Kick Off
    → "เมื่อผู้รับอนุญาตยืนยันใบสั่งซื้อ (Purchase Order) และ/หรือยืนยันใบเสนอราคา หรือเมื่อคู่สัญญาลงนามในสัญญา แล้วแต่เหตุการณ์ใดเกิดขึ้นก่อน"

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

    ── เอกสารแนบท้าย ────────────────────────────────────────────────────

    "Quotation_id"                   : เลขที่ใบเสนอราคาที่อ้างอิงเป็นเอกสารแนบท้าย
    "Quotation_date"                 : วันที่ใบเสนอราคา รูปแบบ "1 มกราคม 2567"
    "Subsidiaries_attachment_status" : ถ้ามีบริษัทในเครือ ให้ใส่ "มีเอกสารแนบท้าย" / ถ้าไม่มีให้ใส่ "ไม่มีเอกสารแนบท้าย"

    ตัวอย่างรูปแบบ JSON ที่ต้องการ:
    {{
        "Contract_id": "123456789",
        "Contract_date": "1 มกราคม 2567",
        "Licensee_company_name": "บริษัท แมงโก้ จำกัด",
        "Licensee_tax_id": "ไม่พบข้อมูล",
        "Optional_modules_rows_1": "ระบบ HR",
        "Optional_month_rows_1": "5000",
        "Text_month_row_1": "ห้าพันบาทถ้วน",
        "Optional_year_rows_1": "60000",
        "Text_year_row_1": "(หกหมื่นบาทถ้วน)",
        "Payment_price_1": "300000",
        "Payment_description_1": "เมื่อผู้รับอนุญาตยืนยันใบสั่งซื้อ (Purchase Order) และ/หรือยืนยันใบเสนอราคา หรือเมื่อคู่สัญญาลงนามในสัญญา แล้วแต่เหตุการณ์ใดเกิดขึ้นก่อน",
        "Payment_price_2": "300000",
        "Payment_description_2": "เมื่อผู้อนุญาตดำเนินการฝึกอบรมการใช้งานระบบ (Training) ตามขอบเขตงานที่กำหนดแล้วเสร็จ และได้แจ้งให้ผู้รับอนุญาตทราบ"
    }}
    """

    response = client.chat.completions.create(
        model="qwen3.6-35b-a3b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
        
    )
    print(f"[DEBUG] Qwen API response received, choices={len(response.choices)}")
    choice = response.choices[0]

    raw_response = None
    if hasattr(choice, 'message'):
        message_obj = choice.message
        if isinstance(message_obj, dict):
            raw_response = message_obj.get('content') or message_obj.get('reasoning')
        else:
            raw_response = getattr(message_obj, 'content', None) or getattr(message_obj, 'reasoning', None)
    elif isinstance(choice, dict):
        raw_response = choice.get('message', {}).get('content') or choice.get('message', {}).get('reasoning')

    if raw_response is None and hasattr(choice, 'reasoning'):
        raw_response = choice.reasoning

    print(f"[DEBUG] raw_response object={type(raw_response).__name__} content={raw_response if raw_response is not None else 'None'}")
    if raw_response is None:
        print(f"[DEBUG] full choice object: {choice}")
        raise HTTPException(
            status_code=500,
            detail="Qwen returned no message content. ตรวจสอบ raw response และ response structure."
        )

    if isinstance(raw_response, bytes):
        raw_response = raw_response.decode('utf-8', errors='ignore')

    print(f"[DEBUG] raw_response len={len(raw_response)} preview={raw_response[:300]!r}")
    clean_json = extract_json_from_qwen_response(raw_response)
    print(f"[DEBUG] clean_json len={len(clean_json)} preview={clean_json[:300]!r}")
    return clean_json

# =================================================================
# Helper: ใส่ตัวนำทาง (invisible marker) ให้กับข้อมูลเพื่อชี้เป้าสำหรับการขีดเส้นใต้
# =================================================================
_MARKER = '\u2063'  # INVISIBLE SEPARATOR (ไม่ปรากฏในเอกสาร Word)


# =================================================================
# Helper: ใส่ตัวนำทาง (invisible marker) ให้กับข้อมูลเพื่อชี้เป้าสำหรับการขีดเส้นใต้
# =================================================================
_MARKER = '\u2063'  # INVISIBLE SEPARATOR (ไม่ปรากฏในเอกสาร Word)

def wrap_values(data):
    if isinstance(data, dict):
        return {k: wrap_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [wrap_values(item) for item in data]
    elif isinstance(data, str):
        # ไม่ขีดเส้นใต้สตริงว่าง แต่ให้ขีดเส้นใต้ "ไม่พบข้อมูล"
        if not data.strip():
            return data

        # ลบอักขระส่วนเกินที่ขอบ (เช่น เครื่่องหมายจุลภาค, คำพูด) ออกไปให้ข้อความ "โล้นๆ" ตามที่ต้องการ
        cleaned_data = data.strip(' \t\n\r\'",')
        return f"{_MARKER}{cleaned_data}{_MARKER}"
    elif data is None:
        return data
    else:
        # Wrap all scalar non-string values so they also get highlighted/underlined
        value_str = str(data)
        if not value_str.strip():
            return value_str
        cleaned_data = value_str.strip(' \t\n\r\'",')
        return f"{_MARKER}{cleaned_data}{_MARKER}"



def wrap_values_richtext(data):
    if isinstance(data, dict):
        return {k: wrap_values_richtext(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [wrap_values_richtext(item) for item in data]
    elif isinstance(data, str) and data.strip():
        rt = RichText()
        rt.add(data, color='FF0000', underline=True, font='TH SarabunPSK', size=28)
        return rt
    elif data is not None:
        rt = RichText()
        rt.add(data, color='FF0000', underline=True, font='TH SarabunPSK', size=28)
        return rt
    return data


# Helper: แยก run ที่มี ★ ออกเป็นหลาย run → ใส่สีแดง+ขีดเส้นใต้เฉพาะส่วนที่ fill
# =================================================================
_WNS  = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
_XSNS = 'http://www.w3.org/XML/1998/namespace'

def _split_run_elem_by_stars(r_elem, full_text):
    parts = full_text.split(_MARKER)
    p_elem = r_elem.getparent()
    idx = list(p_elem).index(r_elem)
    p_elem.remove(r_elem)
    insert_idx = idx
    for i, text in enumerate(parts):
        if not text:
            continue
        is_filled = (i % 2 == 1)
        new_r = deepcopy(r_elem)
        for t in list(new_r.findall(f'{{{_WNS}}}t')):
            new_r.remove(t)
        t_elem = OxmlElement('w:t')
        t_elem.text = text
        if text != text.strip() or text.startswith(' ') or text.endswith(' '):
            t_elem.set(f'{{{_XSNS}}}space', 'preserve')
        new_r.append(t_elem)
        rPr = new_r.find(f'{{{_WNS}}}rPr')
        if rPr is None:
            rPr = OxmlElement('w:rPr')
            new_r.insert(0, rPr)
        if is_filled:
            u = rPr.find(f'{{{_WNS}}}u')
            if u is None:
                u = OxmlElement('w:u')
                rPr.append(u)
            u.set(f'{{{_WNS}}}val', 'single')
            clr = rPr.find(f'{{{_WNS}}}color')
            if clr is None:
                clr = OxmlElement('w:color')
                rPr.append(clr)
            clr.set(f'{{{_WNS}}}val', 'FF0000')
        else:
            for tag in ['u', 'color']:
                el = rPr.find(f'{{{_WNS}}}{tag}')
                if el is not None:
                    rPr.remove(el)
        p_elem.insert(insert_idx, new_r)
        insert_idx += 1

def process_runs_to_underline(doc):
    parts_to_search = [doc.element.body]
    
    for section in doc.sections:
        for part in [
            section.header, section.first_page_header, section.even_page_header,
            section.footer, section.first_page_footer, section.even_page_footer,
        ]:
            if part is not None:
                parts_to_search.append(part._element)
                
    for base_element in parts_to_search:
        for r_elem in base_element.xpath('.//w:r'):
            texts = r_elem.findall(f'{{{_WNS}}}t')
            if not texts:
                continue
            run_text = "".join(t.text for t in texts if t.text)
            if _MARKER in run_text:
                _split_run_elem_by_stars(r_elem, run_text)


# =================================================================
# Helper: ลบไฟล์ชั่วคราว
# =================================================================
def cleanup_temp_files(*filepaths):
    for fp in filepaths:
        try:
            if os.path.exists(fp):
                os.remove(fp)
                print(f"ลบไฟล์ชั่วคราวเรียบร้อย: {fp}")
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการลบไฟล์ชั่วคราว {fp}: {e}")

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

# =================================================================
# Authentication: Login Proxy & Token Verification
# =================================================================
@app.post("/login")
async def login(credentials: LoginRequest):
    """
    Proxy ล็อกอิน: รับ username/password จากหน้าบ้าน
    แล้วส่งต่อไปยัง API ภายนอกเพื่อขอ Token
    """
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
            print(f"[❌ ล้มเหลว] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] userid={credentials.userid} | HTTP {response.status_code}")
            try:
                detail = response.json().get("detail", "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
            except Exception:
                detail = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
            raise HTTPException(status_code=response.status_code, detail=detail)
    except http_requests.exceptions.ConnectionError:
        print(f"[❌ เชื่อมต่อไม่ได้] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] userid={credentials.userid}")
        raise HTTPException(
            status_code=503,
            detail="ไม่สามารถเชื่อมต่อกับระบบยืนยันตัวตนภายนอกได้ กรุณาลองใหม่อีกครั้ง",
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[❌ ข้อผิดพลาด] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] userid={credentials.userid} | {str(e)}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการล็อกอิน: {str(e)}")


async def verify_token(authorization: str = Header(None)):
    """
    Dependency: ตรวจสอบ Token โดยส่งไปยัง API ภายนอก
    ถ้า Token ถูกต้อง คืนข้อมูลผู้ใช้ ถ้าไม่ถูกต้องจะ raise 401
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบก่อนใช้งาน")

    token = authorization.split("Bearer ", 1)[1]
    try:
        response = http_requests.get(
            EXTERNAL_AUTH_VERIFY_URL,
            headers={"X-Mango-Auth": token},
            timeout=15,
        )
        if response.status_code == 200:
            return response.json()  # คืนข้อมูลผู้ใช้
        else:
            raise HTTPException(status_code=401, detail="Token หมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="ไม่สามารถตรวจสอบสิทธิ์การใช้งานได้")


@app.get("/quotation/{quotation_id}")
async def get_quotation(quotation_id: str, authorization: str = Header(None)):
    """
    ดึงข้อมูลใบเสนอราคาจากระบบภายนอก โดยใช้เลขที่ใบเสนอราคา
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบก่อนใช้งาน")

    token = authorization.split("Bearer ", 1)[1]

    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ดึงข้อมูลใบเสนอราคา: {quotation_id}")
        response_quotation = http_requests.get(
            EXTERNAL_QUOTATION_URL,
            params={"docno": quotation_id},
            headers={"X-Mango-Auth": token},
            timeout=30,
        )

        if response_quotation.status_code == 200:
            result_quotation = response_quotation.json()
            print(f"[✅ สำเร็จ] ดึงข้อมูลใบเสนอราคา: {quotation_id}")
            return result_quotation
        else:
            print(f"[❌ ล้มเหลว] ดึงข้อมูลใบเสนอราคา: {quotation_id} | HTTP {response_quotation.status_code}")
            raise HTTPException(
                status_code=response_quotation.status_code,
                detail=f"ไม่สามารถดึงข้อมูลใบเสนอราคาได้ (HTTP {response_quotation.status_code})",
            )
    except HTTPException:
        raise
    except http_requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="ไม่สามารถเชื่อมต่อกับระบบภายนอกได้")
    except Exception as e:
        print(f"[❌ ข้อผิดพลาด] ดึงข้อมูลใบเสนอราคา: {quotation_id} | {str(e)}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการดึงข้อมูล: {str(e)}")


@app.post("/generate-contract")
async def generate_contract(
    payload: quotation,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    authorization: str = Header(None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบก่อนใช้งาน")
    # สร้าง ID เฉพาะและโฟลเดอร์สำหรับเก็บไฟล์ชั่วคราว
    file_id = str(uuid.uuid4())
    temp_dir = os.path.join(os.getcwd(), "temp_files")
    os.makedirs(temp_dir, exist_ok=True)
    output_docx_path = os.path.join(temp_dir, f"contract_{file_id}.docx")

    try:
        parsed_json = payload.result_quotation
        quotation_id = payload.quotation_id
        
        # 2. ทำความสะอาดและกรองข้อมูลใบเสนอราคา
        cleaned_data = filter_and_clean_quotation(parsed_json)
        print(f"[✅ สำเร็จ] กำลังสร้างสัญญาจากใบเสนอราคา: {quotation_id}")
        
        # 4. ใช้ Qwen วิเคราะห์ข้อมูลทางธุรกิจออกมาเป็น JSON ก้อนเดียว
        
        qwen_analysis = analyze_with_qwen(cleaned_data)
        
        print(f"[DEBUG] qwen_analysis len={len(qwen_analysis)} preview={qwen_analysis[:300]!r}")
        try:
            data_from_qwen = try_parse_json(qwen_analysis)
            print(f"[✅ JSON Valid] สำเร็จการแยก JSON จาก Qwen")
            if isinstance(data_from_qwen, dict):
                print(f"[DEBUG] parsed data keys={list(data_from_qwen.keys())[:10]}")
            else:
                print(f"[DEBUG] parsed data type={type(data_from_qwen).__name__}")
        except Exception as e:
            print(f"[❌ JSON Error] ไม่สามารถแยก JSON: {str(e)}")
            print(f"[Debug] Raw Response (truncated): {qwen_analysis[:800]}...")
            raise HTTPException(
                status_code=500,
                detail=f"Qwen ส่งกลับข้อมูลที่ไม่ใช่ JSON: {str(e)}"
            )
        
        # 5. ใส่สัญลักษณ์ ★ เพื่อเตรียมขีดเส้นใต้ และเปิดเทมเพลต Word
        wrapped_data = wrap_values_richtext(data_from_qwen)
        doc = DocxTemplate('template_สัญญาเช่า.docx')
        
        # 6. เรนเดอร์ข้อมูลลงในเทมเพลตและขีดเส้นใต้ส่วนที่ถูกแทนที่
        doc.render(wrapped_data)
        process_runs_to_underline(doc)
        
        # 7. เซฟลงไฟล์ผลลัพธ์ Word
        doc.save(output_docx_path)
        
        # อ่านไฟล์ผลลัพธ์เป็น bytes ก่อน เพื่อป้องกัน race condition
        with open(output_docx_path, "rb") as f:
            file_bytes = f.read()

        # ลบไฟล์ชั่วคราวทั้งหมดทันทีหลังอ่านเสร็จแล้ว
        cleanup_temp_files(output_docx_path)

        print(f"[DEBUG] base_url={QWEN_API_BASE_URL}")
        # แปลงไฟล์ docx เป็น base64 เพื่อส่งผ่าน JSON ได้โดยไม่มีปัญหาขนาด header
        return JSONResponse(content={
            "file_base64": base64.b64encode(file_bytes).decode("ascii"),
            "file_name": f"สัญญา_{quotation_id}.docx",
            "contract_data": data_from_qwen,
        })
        
    except Exception as e:
        # ในกรณีที่เกิดความผิดพลาด ลบไฟล์ชั่วคราวทันทีเพื่อไม่ให้ค้างคา
        cleanup_temp_files(output_docx_path)
        print(f"เกิดข้อผิดพลาดในระบบ: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการประมวลผลเอกสาร: {str(e)}")

# =================================================================
# สั่งรันเว็บเซิร์ฟเวอร์
# =================================================================
if __name__ == "__main__":
    import uvicorn
    # รันบน localhost พอร์ต 8000
    uvicorn.run("back_end:app", host="127.0.0.1", port=8000, reload=True)