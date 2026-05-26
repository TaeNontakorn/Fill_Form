import io
import os
import json
import base64
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
from google import genai
from pydantic import BaseModel, Field
import sys
import uuid
import shutil
from dotenv import load_dotenv
from copy import deepcopy
from docxtpl import DocxTemplate
from docx.oxml import OxmlElement

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# บังคับใช้ UTF-8 สำหรับการแสดงผลบน Terminal
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

# ตั้งค่าโมเดล Gemini
API_KEY = os.environ.get("API_KEY") or os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# =================================================================
# Schema สำหรับ Structured Output
# =================================================================
class TableItem(BaseModel): 
    specification: str = Field(description="รายละเอียดสินค้า รายละเอียดบริการ หรือข้อกำหนด/รายการในตาราง")
    total_amount: str = Field(description="ราคารวม จำนวนเงิน หรือมูลค่าประจำรายการนั้น")

class OCRResponse(BaseModel):
    all_text: str = Field(description="ข้อความทั่วไปทั้งหมดจากเอกสาร ไม่รวมข้อมูลตาราง")
    table_data: list[TableItem] = Field(description="ข้อมูลตาราง")

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
    Concurrent_users: str = Field(description="จำนวนผู้ใช้งานพร้อมกัน (Concurrent Users) ที่รวมมากับโปรแกรม")
    Additional_concurrent_users: str = Field(description="จำนวนผู้ใช้งานพร้อมกันแบบซื้อเพิ่มเติม")
    Add_multi_company_count: str = Field(description="จำนวนบริษัทในเครือ (Add Multi Company)")
    Optional_module_count: str = Field(description="จำนวนระบบโมดูลเสริม (Optional Modules) ที่เลือกใช้งานเพิ่มเติม")
    Optional_module_details: str = Field(description="รายชื่อระบบโมดูลเสริม พร้อมระบุราคาต่อเดือนเป็นตัวเลขและตัวหนังสือ")
    Implement_package_name: str = Field(description="ชื่อแพคเกจสำหรับการวางระบบซอฟต์แวร์ (Implement)")
    Implement_price: str = Field(description="มูลค่าสัญญางานวางระบบ ระบุทั้งตัวเลขและตัวหนังสือ")
    Implement_payment_terms: str = Field(description="เงื่อนไขและงวดการชำระเงินสำหรับค่าวางระบบ")
    Deposit_amount: str = Field(description="จำนวนเงินมัดจำประกันการใช้โปรแกรมล่วงหน้า 2 เดือน ระบุทั้งตัวเลขและตัวหนังสือ")
    Customize_man_days: str = Field(description="จำนวนวันทำงาน (Man-day) สำหรับการพัฒนาโปรแกรมเพิ่มเติม")
    Customize_rate_per_day: str = Field(description="อัตราค่าบริการพัฒนาโปรแกรมเพิ่มเติมต่อ 1 วันทำงาน ระบุทั้งตัวเลขและตัวหนังสือ")
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
# 1. ฟังก์ชันครอป PDF
# =================================================================
def crop_pdf(input_path: str, output_path: str):
    print(f"กำลังทำการครอปเอกสาร: {input_path}...")
    doc = fitz.open(input_path)
    for page in doc:
        crop_box = fitz.Rect(0, 90, page.rect.width, page.rect.height - 170) 
        page.set_cropbox(crop_box)
    doc.save(output_path)
    doc.close()
    print(f"บันทึกเอกสารที่ครอปแล้วสำเร็จ\n")

# =================================================================
# 2. ฟังก์ชัน Gemini อ่านเอกสาร (ดวงตา)
# =================================================================
def extract_data_from_pdf(pdf_path: str):
    print(f"กำลังส่งให้ Gemini ประมวลผลภาพเอกสาร...")
    images = []
    doc_cut = fitz.open(pdf_path)
    for page in doc_cut:
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img.load()  
        images.append(img)
    doc_cut.close()

    prompt = """
    ดึงข้อความทั้งหมดจากภาพนี้ แยกส่วนข้อความทั่วไปและส่วนตาราง 
    เฉพาะตารางเอาแค่คอลัมน์ "Specification" และ "Total amount"
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-pro", 
        contents=images + [prompt],
        config={
            "response_mime_type": "application/json",
            "response_schema": OCRResponse,
        }
    )
    return response.text

# =================================================================
# 3. ฟังก์ชันสกัดข้อมูลจากเอกสารด้วย Gemini (สมอง)
# =================================================================
def analyze_with_gemini(parsed_json):
    all_text = parsed_json.get("all_text", "")
    table_items = parsed_json.get("table_data", [])
    
    table_string = ""
    if table_items:
        table_string = "ข้อมูลรายการสินค้า/บริการ:\n"
        for idx, item in enumerate(table_items, 1):
            table_string += f"   - รายการที่ {idx}: {item['specification']} (มูลค่า: {item['total_amount']})\n"
    
    document_content = f"--- ข้อมูลทั่วไปในเอกสาร ---\n{all_text}\n\n--- ตารางรายการ ---\n{table_string}"
    
    prompt = f"""
    นี่คือข้อมูลที่อ่านได้จากเอกสาร:
    {document_content}
    
    หน้าที่ของคุณคือ สกัดข้อมูลจากเอกสารด้านบนตามหัวข้อที่กำหนด และต้องตอบกลับมาในรูปแบบ JSON เท่านั้น
    
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
    "Concurrent_users" : จำนวนผู้ใช้งานพร้อมกัน (Concurrent Users) ที่รวมมากับโปรแกรม
    "Mandays_count" : จำนวนวันทำงาน (Man-day) สำหรับการวางระบบซอฟต์แวร์ (Implement)
    "Manday_price" : ราคาต่อวันสำหรับการวางระบบซอฟต์แวร์ (Implement)
    "Additional_concurrent_users" : จำนวนผู้ใช้งานพร้อมกันแบบซื้อเพิ่มเติม
    "Add_multi_company_count" : จำนวนบริษัทในเครือ (Add Multi Company)
    "Optional_module_count" : จำนวนระบบโมดูลเสริม (Optional Modules) ที่เลือกใช้งานเพิ่มเติม
    "Optional_module_details" : รายชื่อระบบโมดูลเสริม พร้อมระบุราคาต่อเดือนเป็นตัวเลขและตัวหนังสือ
    "Implement_package_name" : ชื่อแพคเกจสำหรับการวางระบบซอฟต์แวร์ (Implement)
    "Implement_price" : มูลค่าสัญญางานวางระบบ ระบุทั้งตัวเลขและตัวหนังสือ
    "Implement_payment_terms" : เงื่อนไขและงวดการชำระเงินสำหรับค่าวางระบบ
    "Deposit_amount" : จำนวนเงินมัดจำประกันการใช้โปรแกรมล่วงหน้า 2 เดือน ระบุทั้งตัวเลขและตัวหนังสือ
    "Customize_man_days" : จำนวนวันทำงาน (Man-day) สำหรับการพัฒนาโปรแกรมเพิ่มเติม
    "Customize_rate_per_day" : อัตราค่าบริการพัฒนาโปรแกรมเพิ่มเติมต่อ 1 วันทำงาน ระบุทั้งตัวเลขและตัวหนังสือ
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
    
    response = client.models.generate_content(
        model="gemini-2.5-pro", 
        contents=[prompt],
        config={
            "response_mime_type": "application/json",
            "response_schema": ContractResponse,
        }
    )
    return response.text

# =================================================================
# Helper: ใส่ตัวนำทาง ★ ให้กับข้อมูลเพื่อชี้เป้าสำหรับการขีดเส้นใต้
# =================================================================
def wrap_values(data):
    if isinstance(data, dict):
        return {k: wrap_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [wrap_values(item) for item in data]
    elif isinstance(data, str):
        # ไม่ขีดเส้นใต้คำว่า "ไม่พบข้อมูล" หรือค่าว่าง
        if data == "ไม่พบข้อมูล" or not data.strip():
            return data
        return f"★{data}★"
    else:
        return data


# Helper: แยก run ที่มี ★ ออกเป็นหลาย run → ใส่สีแดง+ขีดเส้นใต้เฉพาะส่วนที่ fill
# =================================================================
_WNS  = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
_XSNS = 'http://www.w3.org/XML/1998/namespace'

def _split_run_by_stars(run):
    full_text = run.text
    parts = full_text.split('★')
    r_elem = run._r
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
        if text != text.strip():
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


def _process_paragraphs(paragraphs):
    for p in paragraphs:
        runs_to_fix = [r for r in p.runs if '★' in r.text]
        for r in runs_to_fix:
            _split_run_by_stars(r)


# Helper: ค้นหาข้อความที่มี ★ ในไฟล์ Word ตั้งค่าขีดเส้นใต้+สีแดง และลบ ★ ออก
# =================================================================
def process_runs_to_underline(doc):
    # 1. ย่อหน้าปกติ
    _process_paragraphs(doc.paragraphs)
    # 2. ตาราง
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                _process_paragraphs(cell.paragraphs)
                for nested_table in cell.tables:
                    for nested_row in nested_table.rows:
                        for nested_cell in nested_row.cells:
                            _process_paragraphs(nested_cell.paragraphs)
    # 3. Header และ Footer
    for section in doc.sections:
        for part in [
            section.header, section.first_page_header, section.even_page_header,
            section.footer, section.first_page_footer, section.even_page_footer,
        ]:
            if part:
                _process_paragraphs(part.paragraphs)

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

@app.post("/generate-contract")
async def generate_contract(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    # ตรวจสอบว่าเป็นไฟล์ PDF หรือไม่
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="กรุณาอัพโหลดเฉพาะไฟล์ PDF เท่านั้น")
    
    # สร้าง ID เฉพาะและโฟลเดอร์สำหรับเก็บไฟล์ชั่วคราว
    file_id = str(uuid.uuid4())
    temp_dir = os.path.join(os.getcwd(), "temp_files")
    os.makedirs(temp_dir, exist_ok=True)
    
    input_pdf_path = os.path.join(temp_dir, f"input_{file_id}.pdf")
    cropped_pdf_path = os.path.join(temp_dir, f"cropped_{file_id}.pdf")
    output_docx_path = os.path.join(temp_dir, f"contract_{file_id}.docx")
    
    try:
        # 1. เซฟไฟล์ PDF ที่อัพโหลดเข้ามาลงไดรฟ์
        with open(input_pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. ครอป PDF เพื่อเอาหัว/ท้ายออก
        crop_pdf(input_pdf_path, cropped_pdf_path)
        
        # 3. ใช้ Gemini แกะข้อความทั่วไปและข้อความในตาราง (OCR)
        raw_json_result = extract_data_from_pdf(cropped_pdf_path)
        parsed_json = json.loads(raw_json_result)
        
        # 4. ใช้ Gemini วิเคราะห์ข้อมูลทางธุรกิจออกมาเป็น JSON ก้อนเดียว
        gemini_analysis = analyze_with_gemini(parsed_json)
        data_from_gemini = json.loads(gemini_analysis)
        
        # 5. ใส่สัญลักษณ์ ★ เพื่อเตรียมขีดเส้นใต้ และเปิดเทมเพลต Word
        wrapped_data = wrap_values(data_from_gemini)
        doc = DocxTemplate('template.docx')
        
        # 6. เรนเดอร์ข้อมูลลงในเทมเพลตและขีดเส้นใต้ส่วนที่ถูกแทนที่
        doc.render(wrapped_data)
        process_runs_to_underline(doc)
        
        # 7. เซฟลงไฟล์ผลลัพธ์ Word
        doc.save(output_docx_path)
        
        # อ่านไฟล์ผลลัพธ์เป็น bytes ก่อน เพื่อป้องกัน race condition
        with open(output_docx_path, "rb") as f:
            file_bytes = f.read()

        # ลบไฟล์ชั่วคราวทั้งหมดทันทีหลังอ่านเสร็จแล้ว (ปลอดภัยกว่า BackgroundTask)
        cleanup_temp_files(input_pdf_path, cropped_pdf_path, output_docx_path)

        # แปลงไฟล์ docx เป็น base64 เพื่อส่งผ่าน JSON ได้โดยไม่มีปัญหาขนาด header
        original_name_without_ext = os.path.splitext(file.filename)[0]
        return JSONResponse(content={
            "file_base64": base64.b64encode(file_bytes).decode("ascii"),
            "file_name": f"สัญญา_{original_name_without_ext}.docx",
            "contract_data": data_from_gemini,
        })
        
    except Exception as e:
        # ในกรณีที่เกิดความผิดพลาด ลบไฟล์ชั่วคราวทันทีเพื่อไม่ให้ค้างคา
        cleanup_temp_files(input_pdf_path, cropped_pdf_path, output_docx_path)
        print(f"เกิดข้อผิดพลาดในระบบ: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการประมวลผลเอกสาร: {str(e)}")

# =================================================================
# สั่งรันเว็บเซิร์ฟเวอร์
# =================================================================
if __name__ == "__main__":
    import uvicorn
    # รันบน localhost พอร์ต 8000
    uvicorn.run("back_end:app", host="127.0.0.1", port=8000, reload=True)