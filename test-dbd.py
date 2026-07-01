"""
Extractor สำหรับเอกสาร "ข้อมูลบริษัท" จากระบบ DBD DataWarehouse+
(https://datawarehouse.dbd.go.th/company/profile/)

วิธีใช้:
    python extract_dbd_profile.py Company_Profile.pdf
"""

import re
import sys
import json
import pdfplumber


def clean(text: str) -> str:
    """รวมช่องว่าง/ขึ้นบรรทัดใหม่ที่ไม่จำเป็นให้เหลืออันเดียว"""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()


def split_code_desc(value: str):
    """แยก 'รหัส : คำอธิบาย' เช่น '68101 : การซื้อและการขาย...' """
    value = clean(value)
    m = re.match(r"^(\d{4,6})\s*:\s*(.+)$", value)
    if m:
        return {"code": m.group(1), "description": m.group(2)}
    return {"code": None, "description": value}


def extract_dbd_profile(pdf_path: str) -> dict:
    full_text_pages = []
    raw_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            full_text_pages.append(page.extract_text() or "")
            for table in page.extract_tables():
                raw_rows.extend(table)

    # header เอาจากบรรทัดข้อความหน้าที่ 1 (ไม่ได้อยู่ในตาราง)
    header_text = full_text_pages[0] if full_text_pages else ""
    company_name = None
    print_datetime = None

    m_name = re.search(r"ข้อมูล\s*\n(.+)", header_text)
    if m_name:
        company_name = clean(m_name.group(1))

    m_dt = re.search(r"วันที่สั่งพิมพ์\s*:\s*([\d/]+)\s*เวลา\s*:\s*([\d:]+)", header_text)
    if m_dt:
        print_datetime = {"date": m_dt.group(1), "time": m_dt.group(2)}

    # แปลง raw_rows -> dict โดย key = label (ไม่มี ':' ต่อท้าย, trim whitespace/\n)
    data = {}
    for row in raw_rows:
        if len(row) < 2:
            continue
        label = clean(row[0]).rstrip(":").strip()
        value = row[1] if row[1] is not None else ""
        data[label] = value

    result = {
        "company_name": company_name,
        "print_datetime": print_datetime,
        "registration_number": clean(data.get("เลขทะเบียนนิติบุคคล", "")),
        "entity_type": clean(data.get("ประเภทนิติบุคคล", "")),
        "registration_date": clean(data.get("วันที่จดทะเบียนจัดตั้ง", "")),
        "status": clean(data.get("สถานะนิติบุคคล", "")),
        "registered_capital_baht": clean(
            data.get("ทุนจดทะเบียน (บาท)", "")
        ).replace(",", ""),
        "address": clean(data.get("ที่ตั้ง", "")),
        "business_category_at_registration": split_code_desc(
            data.get("หมวดธุรกิจตอนจดทะเบียน", "")
        ),
        "objective_at_registration": clean(data.get("วัตถุประสงค์ตอนจดทะเบียน", "")),
        "business_category_latest_financial": None,
        "objective_latest_financial": None,
        "financial_statement_years": [],
        "directors": [],
        "signing_authority": clean(data.get("คณะกรรมการลงชื่อผูกพัน", "")),
    }

    # label ของสองรายการนี้ถูกตัดบรรทัดเป็น 2 บรรทัดใน PDF ต้นฉบับ
    # ("หมวดธุรกิจ\n(มาจากงบการเงินปีล่าสุด) :") -> หลัง clean() label จะกลายเป็น
    # "หมวดธุรกิจ (มาจากงบการเงินปีล่าสุด)"
    for label, value in data.items():
        norm_label = clean(label)
        if norm_label.startswith("หมวดธุรกิจ") and "งบการเงิน" in norm_label:
            result["business_category_latest_financial"] = split_code_desc(value)
        elif norm_label.startswith("วัตถุประสงค์") and "งบการเงิน" in norm_label:
            result["objective_latest_financial"] = clean(value)

    # ปีที่ส่งงบการเงิน -> list of str
    years_raw = clean(data.get("ปีที่ส่งงบการเงิน", ""))
    result["financial_statement_years"] = years_raw.split() if years_raw else []

    # กรรมการ -> list โดยตัดเลขลำดับ "1." "2." และ "/" ท้ายชื่อออก
    directors_raw = data.get("กรรมการ", "")
    directors_list = []
    for line in directors_raw.split("\n"):
        line = line.strip().rstrip("/").strip()
        if not line:
            continue
        line = re.sub(r"^\d+\.\s*", "", line)
        directors_list.append(line)
    result["directors"] = directors_list

    result["signing_authority"] = result["signing_authority"].rstrip("/").strip()

    return result


if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "Company_Profile.pdf"
    data = extract_dbd_profile(pdf_path)
    print(json.dumps(data, ensure_ascii=False, indent=2))