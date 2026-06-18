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
from docxtpl import DocxTemplate
from docx.oxml import OxmlElement

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
    Contract_start_date: str = Field(description="วันที่เริ่มต้นสัญญา")
    Contract_end_date: str = Field(description="วันที่สิ้นสุดสัญญา")
    License_fee: str = Field(description="จำนวนเงินค่าสิทธิการใช้โปรแกรม (License fee) รายเดือน ระบุทั้งตัวเลขและตัวหนังสือ")
    License_fee_month: str = Field(description="ค่าสิทธิการใช้โปรแกรม (License fee) รายเดือน ระบุเป็นตัวเลข")
    License_fee_year: str = Field(description="ค่าสิทธิการใช้โปรแกรม (License fee) รายปี ระบุทั้งตัวเลขและตัวหนังสือ")
    Cloud_usage_description: str = Field(description="รายละเอียดการใช้งานระบบ Cloud")
    Concurrent_users: str = Field(description="จำนวนผู้ใช้งานพร้อมกัน (Concurrent Users) ที่รวมมากับโปรแกรม")
    Additional_concurrent_users: str = Field(description="จำนวนผู้ใช้งานพร้อมกันแบบซื้อเพิ่มเติม")
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

# =================================================================
# 3. ฟังก์ชันสกัดข้อมูลจากเอกสารด้วย Qwen
# =================================================================
def analyze_with_qwen(parsed_json):
    document_content = json.dumps(parsed_json, ensure_ascii=False, indent=2)
    
    prompt = f"""
    นี่คือข้อมูลใบเสนอราคาจากระบบ (JSON Format):
    {document_content}
    
    หน้าที่ของคุณคือ สกัดข้อมูลจากใบเสนอราคานี้ตามหัวข้อที่กำหนด และต้องตอบกลับมาในรูปแบบ JSON เท่านั้น
    
    [กฎข้อบังคับที่ต้องทำตามอย่างเคร่งครัด]
    1. ห้ามมีข้อความเกริ่นนำ ข้อความสรุป หรือคำอธิบายใดๆ ทั้งสิ้น ให้ตอบกลับมาแค่โครงสร้างปีกกา {{...}} ของ JSON เท่านั้น
    2. หากหัวข้อไหน "ไม่พบข้อมูล" ในเอกสาร ให้ใส่ค่าเป็น "ไม่พบข้อมูล" (ห้ามแต่งเติมหรือเดาข้อมูลเองเด็ดขาด)
    3. ใช้ชื่อ Key ตามที่ระบุด้านล่างนี้เป๊ะๆ:

    "Contract_id" : สัญญาเลขที่
    "Contract_date" : วันที่ทำสัญญา
    "Customer_company_name" : ชื่อบริษัทลูกค้า (ผู้รับอนุญาต)
    "Customer_tax_id" : เลขทะเบียนนิติบุคคลของบริษัทลูกค้า
    "Customer_director_name" : ชื่อกรรมการบริษัท หรือผู้รับมอบอำนาจของบริษัทลูกค้า
    "Customer_address" : ที่ตั้งสำนักงานของบริษัทลูกค้า
    "Standard_module_count" : จำนวน Module มาตรฐานที่ได้รับสิทธิ
    "Standard_module_name" : ชื่อแพ็กเกจหรือประเภทสำหรับ Module มาตรฐาน
    "Standard_users_count" : จำนวนผู้ใช้งานเบื้องต้นสำหรับระบบมาตรฐาน
    "Contract_start_date" : วันที่เริ่มต้นสัญญา
    "Contract_end_date" : วันที่สิ้นสุดสัญญา
    "License_fee" : จำนวนเงินค่าสิทธิการใช้โปรแกรม (License fee) รายเดือน ระบุทั้งตัวเลขและตัวหนังสือ
    "License_fee_month" : ค่าสิทธิการใช้โปรแกรม (License fee) รายเดือน ระบุเป็นตัวเลข
    "License_fee_year" : ค่าสิทธิการใช้โปรแกรม (License fee) รายปี ระบุทั้งตัวเลขและตัวหนังสือ
    "Cloud_usage_description" : รายละเอียดการใช้งานระบบ Cloud
    "Concurrent_users" : จำนวนผู้ใช้งานพร้อมกัน (Concurrent Users) ที่รวมมากับโปรแกรม
    "Additional_concurrent_users" : จำนวนผู้ใช้งานพร้อมกันแบบซื้อเพิ่มเติม
    "Add_multi_company_count" : จำนวนบริษัทในเครือ (Add Multi Company)
    "Add_multi_rate_price" : ราคาค่าบริการ Add Multi Company ระบุทั้งตัวเลขและตัวหนังสือ
    "Optional_module_count" : จำนวนระบบโมดูลเสริม (Optional Modules) ที่เลือกใช้งานเพิ่มเติม
    "Optional_module_details" : รายชื่อระบบโมดูลเสริม พร้อมระบุราคาต่อเดือนเป็นตัวเลขและตัวหนังสือ
    "Implement_package_name" : ชื่อแพคเกจสำหรับการวางระบบซอฟต์แวร์ (Implement)
    "Implement_price" : มูลค่าสัญญางานวางระบบ ระบุทั้งตัวเลขและตัวหนังสือ
    "Implement_mandays" : จำนวนวันทำงาน (Man-day) สำหรับการวางระบบซอฟต์แวร์ (Implement)
    "Implement_payment_terms" : เงื่อนไขและงวดการชำระเงินสำหรับค่าวางระบบ โดยต้องระบุคำว่า "ชำระ" ต่อท้ายคำว่า "งวดที่ X" เสมอ (เช่น "งวดที่ 1 ชำระ 30%") รูปแบบที่ต้องการเช่น "งวดที่ 1 ชำระ 30% ชำระเมื่อเริ่มโครงการและแผนดำเนินงาน (Kick Off Project) เป็นจำนวนเงิน 90,000.00 บาท"
    "Deposit_amount" : จำนวนเงินมัดจำประกันการใช้โปรแกรมล่วงหน้า 2 เดือน ระบุทั้งตัวเลขและตัวหนังสือ
    "Customize_man_days" : จำนวนวันทำงาน (Man-day) สำหรับการพัฒนาโปรแกรมเพิ่มเติม
    "Customize_rate_per_day" : อัตราค่าบริการพัฒนาโปรแกรมเพิ่มเติมต่อ 1 วันทำงาน ระบุทั้งตัวเลขและตัวหนังสือ
    "Support_rate_per_manday" : อัตราค่าบริการ Support ต่อ 1 วันทำงาน (Man-day) ระบุเป็นตัวเลข
    "Support_rate_per_manday_text" : อัตราค่าบริการ Support ต่อ 1 วันทำงาน (Man-day) ระบุเป็นตัวหนังสือ
    "Mandays_count" : จำนวนวันทำงาน (Man-day) สำหรับการวางระบบซอฟต์แวร์ (Implement)
    "Manday_price" : ราคาต่อวันสำหรับการวางระบบซอฟต์แวร์ (Implement)
    "Quotation_id" : เลขที่ใบเสนอราคาที่นำมาอ้างอิงเป็นเอกสารแนบท้าย
    "Quotation_date" : วันที่ของใบเสนอราคา
    "Customer_company_signature_name" : ชื่อบริษัทลูกค้าสำหรับประทับตราในหน้าลงนาม
    "Customer_authorized_signature" : ลายมือชื่อและชื่อตัวบรรจงของผู้มีอำนาจลงนามฝ่ายลูกค้า
    "Customer_position" : ตำแหน่งของผู้มีอำนาจลงนามฝ่ายลูกค้า
    "Customer_email" : อีเมลของผู้มีอำนาจลงนามฝ่ายลูกค้า
    "Customer_witness_signature" : ลายมือชื่อพยานฝ่ายลูกค้า
    "Customer_witness_email" : อีเมลของพยานฝ่ายลูกค้า

    ตัวอย่างรูปแบบ JSON ที่ต้องการ:
    {{
        "Contract_id": "123456789",
        "Contract_date": "1 มกราคม 2567",
        "Customer_company_name": "บริษัท มังโก จำกัด",
        "Customer_tax_id": "ไม่พบข้อมูล"
    }}
    """
    
    response = client.chat.completions.create(
        model="qwen3.6-35b-a3b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        
    )
    print(f"[DEBUG] Qwen API response received, choices={len(response.choices)}")
    choice = response.choices[0]
    raw_response = None
    if hasattr(choice, 'message'):
        raw_response = getattr(choice.message, 'content', None)
        if raw_response is None and isinstance(choice.message, dict):
            raw_response = choice.message.get('content')
    elif isinstance(choice, dict):
        raw_response = choice.get('message', {}).get('content')

    print(f"[DEBUG] raw_response object={type(raw_response).__name__} content={raw_response if raw_response is not None else 'None'}")
    if raw_response is None:
        print(f"[DEBUG] full choice object: {choice}")
        raise HTTPException(
            status_code=500,
            detail="Qwen returned no message content. ตรวจสอบ raw response และ response structure."
        )

    print(f"[DEBUG] raw_response len={len(raw_response)} preview={raw_response[:300]!r}")
    clean_json = extract_json_from_qwen_response(raw_response)
    print(f"[DEBUG] clean_json len={len(clean_json)} preview={clean_json[:300]!r}")
    return clean_json

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
        # ไม่ขีดเส้นใต้คำว่า "ไม่พบข้อมูล" หรือค่าว่าง
        if data == "ไม่พบข้อมูล" or not data.strip():
            return data
        
        # ลบอักขระส่วนเกินที่ขอบ (เช่น เครื่องหมายจุลภาค, คำพูด) ออกไปให้ข้อความ "โล้นๆ" ตามที่ต้องการ
        cleaned_data = data.strip(' \t\n\r\'",')
        return f"{_MARKER}{cleaned_data}{_MARKER}"
    else:
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
    parts_to_search = [doc.docx.element.body]
    
    for section in doc.docx.sections:
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
        
        print(f"[✅ สำเร็จ] กำลังสร้างสัญญาจากใบเสนอราคา: {quotation_id}")
        
        # 4. ใช้ Qwen วิเคราะห์ข้อมูลทางธุรกิจออกมาเป็น JSON ก้อนเดียว
        qwen_analysis = analyze_with_qwen(parsed_json)
        print(f"[DEBUG] qwen_analysis len={len(qwen_analysis)} preview={qwen_analysis[:300]!r}")
        try:
            data_from_qwen = json.loads(qwen_analysis)
            print(f"[✅ JSON Valid] สำเร็จการแยก JSON จาก Qwen")
            print(f"[DEBUG] parsed data keys={list(data_from_qwen.keys())[:10]}")
        except json.JSONDecodeError as e:
            print(f"[❌ JSON Error] ไม่สามารถแยก JSON: {str(e)}")
            print(f"[Debug] Raw Response: {qwen_analysis[:400]}...")
            raise HTTPException(
                status_code=500,
                detail=f"Qwen ส่งกลับข้อมูลที่ไม่ใช่ JSON: {str(e)}"
            )
        
        # 5. ใส่สัญลักษณ์ ★ เพื่อเตรียมขีดเส้นใต้ และเปิดเทมเพลต Word
        wrapped_data = wrap_values(data_from_qwen)
        doc = DocxTemplate('1.สัญญาอนุญาตให้ใช้สิทธิการใช้โปรแกรมวันอังคาร.docx')
        
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