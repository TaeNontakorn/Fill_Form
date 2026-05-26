import streamlit as st
import requests
import os
import json
import base64

# =================================================================
# การตั้งค่าหน้าเว็บและดีไซน์ความสวยงาม (Aesthetics)
# =================================================================
st.set_page_config(
    page_title="Mango Auto Contract Generator",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom CSS สำหรับดีไซน์พรีเมียม (Glassmorphism & Gradients)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Sarabun:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Sarabun', 'Outfit', sans-serif;
    }
    
    /* ซ่อนแถบเครื่องมือของ Streamlit เพื่อความสะอาดตา */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* พื้นหลังไล่เฉดสีพรีเมียม */
    .stApp {
        background: radial-gradient(circle at 50% 50%, #1e1e2f 0%, #11111b 100%);
        color: #f3f4f6;
    }
    
    /* การ์ดต้อนรับด้านบนพร้อมสีรุ้งไล่ระดับ */
    .header-container {
        text-align: center;
        padding: 2.5rem 1.5rem;
        background: rgba(255, 255, 255, 0.03);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }
    
    .main-title {
        background: linear-gradient(135deg, #ff7e5f 0%, #feb47b 50%, #86e3ce 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        font-family: 'Sarabun', sans-serif;
    }
    
    .subtitle {
        color: #a1a1aa;
        font-size: 1.1rem;
        font-weight: 300;
    }
    
    /* ส่วนแสดงความก้าวหน้าการทำงาน (Steps) */
    .steps-container {
        display: flex;
        justify-content: space-between;
        margin-top: 1.5rem;
        gap: 10px;
    }
    
    .step-card {
        flex: 1;
        background: rgba(255, 255, 255, 0.02);
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.04);
        text-align: center;
    }
    
    .step-icon {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
    }
    
    .step-title {
        font-size: 0.9rem;
        font-weight: 600;
        color: #e4e4e7;
    }
    
    /* กล่องอัปโหลดไฟล์ */
    .uploadedFile {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 2px dashed rgba(255, 255, 255, 0.2) !important;
        border-radius: 12px !important;
        padding: 2rem !important;
    }
    
    /* ดีไซน์ปุ่มกดขนาดใหญ่ไล่สีสว่าง */
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.75rem 2rem !important;
        border-radius: 12px !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6) !important;
        background: linear-gradient(135deg, #4f46e5 0%, #9333ea 100%) !important;
    }
    
    /* ปุ่มดาวน์โหลดไฟล์ */
    .stDownloadButton>button {
        width: 100%;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.75rem 2rem !important;
        border-radius: 12px !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4) !important;
        transition: all 0.3s ease !important;
    }
    
    .stDownloadButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.6) !important;
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
    }

    /* กล่องแสดงผลข้อมูลที่ AI สกัดได้ */
    .data-result-box {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.5rem 1.8rem;
        margin-top: 1.5rem;
    }

    .data-result-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #e4e4e7;
        margin-bottom: 1rem;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }

    .data-row {
        display: flex;
        gap: 0.5rem;
        padding: 0.35rem 0;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        font-size: 0.92rem;
        align-items: flex-start;
        line-height: 1.5;
    }

    .data-row:last-child {
        border-bottom: none;
    }

    .data-key {
        color: #a1a1aa;
        min-width: 220px;
        flex-shrink: 0;
    }

    .data-value {
        color: #ff6b6b;
        font-weight: 500;
        word-break: break-word;
    }

    .data-value.not-found {
        color: #52525b;
        font-style: italic;
        font-weight: 400;
    }
</style>
""", unsafe_allow_html=True)

# API Endpoint ของ FastAPI Back-end
API_URL = "https://fill-form-8163.onrender.com"

# =================================================================
# ส่วนแสดงผล UI หน้าแรก
# =================================================================
st.markdown("""
<div class="header-container">
    <div class="main-title">Mango Auto Contract Generator</div>
    <div class="subtitle">ระบบวิเคราะห์ใบเสนอราคาและออกสัญญาจัดซื้ออัตโนมัติ</div>
    <div class="steps-container">
        <div class="step-card">
            <div class="step-icon">📤</div>
            <div class="step-title">1. อัปโหลดใบเสนอราคา</div>
        </div>
        <div class="step-card">
            <div class="step-icon">🧠</div>
            <div class="step-title">2. AI สกัดและวิเคราะห์</div>
        </div>
        <div class="step-card">
            <div class="step-icon">📥</div>
            <div class="step-title">3. ดาวน์โหลดสัญญา</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ส่วนอัปโหลดไฟล์ PDF
st.write("### 📄 อัปโหลดใบเสนอราคาของคุณ")
uploaded_file = st.file_uploader(
    "ลากและวางไฟล์ PDF ใบเสนอราคา (Quotation) ของคุณลงที่นี่", 
    type=["pdf"],
    label_visibility="collapsed"
)

if uploaded_file is not None:
    st.info(f"📂 เลือกไฟล์สำเร็จ: **{uploaded_file.name}** ({uploaded_file.size / 1024:.2f} KB)")
    
    # ปุ่มเริ่มสร้างสัญญา
    if st.button("เริ่มสร้างเอกสารสัญญา 🚀"):
        with st.spinner("AI กำลังครอปไฟล์และสกัดข้อมูลด้วยดวงตาอัจฉริยะ (Gemini)... โปรดรอสักครู่"):
            try:
                # ส่งข้อมูลแบบ Multipart Form ไปยัง API
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                response = requests.post(API_URL, files=files, timeout=180)
                
                if response.status_code == 200:
                    # Backend ส่งกลับมาเป็น JSON: {file_base64, file_name, contract_data}
                    result = response.json()
                    file_bytes = base64.b64decode(result["file_base64"])
                    file_name  = result.get("file_name", f"สัญญา_{os.path.splitext(uploaded_file.name)[0]}.docx")
                    contract_data = result.get("contract_data", {})

                    st.success("🎉 AI ดึงข้อมูลและสร้างสัญญา Word (.docx) สำเร็จแล้ว!")

                    # แสดงปุ่มดาวน์โหลดไฟล์
                    st.download_button(
                        label="📥 ดาวน์โหลดสัญญา Word (.docx)",
                        data=file_bytes,
                        file_name=file_name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

                    # แสดงผลข้อมูลที่ AI สกัดได้ โดยค่าที่ fill เป็นสีแดง
                    if contract_data:
                        rows_html = ""
                        for key, value in contract_data.items():
                            display_key = key.replace("_", " ")
                            is_empty = (not value or str(value).strip() == "ไม่พบข้อมูล")
                            value_class = "data-value not-found" if is_empty else "data-value"
                            safe_value = str(value).replace("<", "&lt;").replace(">", "&gt;")
                            rows_html += f"""
                            <div class="data-row">
                                <span class="data-key">{display_key}</span>
                                <span class="{value_class}">{safe_value}</span>
                            </div>"""

                        st.markdown(f"""
                        <div class="data-result-box">
                            <div class="data-result-title">🔍 ข้อมูลที่ AI สกัดได้จากเอกสาร
                                <span style="font-size:0.8rem; color:#71717a; font-weight:400; margin-left:0.5rem;">
                                    (ข้อความสีแดง = ค่าที่ถูกเติมลงสัญญา)
                                </span>
                            </div>
                            {rows_html}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    try:
                        error_detail = response.json().get("detail", "เซิร์ฟเวอร์ตอบกลับด้วยข้อผิดพลาดที่ไม่ทราบสาเหตุ")
                    except Exception:
                        error_detail = "ไม่สามารถเชื่อมต่อหรืออ่านการตอบกลับของ Back-end ได้"
                    st.error(f"❌ เกิดข้อผิดพลาดจากฝั่ง Back-end: {error_detail}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ ไม่สามารถเชื่อมต่อกับ Back-end API ได้ กรุณาเปิดเซิร์ฟเวอร์ FastAPI (`uvicorn back_end:app`) ก่อนเริ่มรันหน้าเว็บ")
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดระหว่างส่งข้อมูล: {str(e)}")
else:
    # แจ้งเตือนเพื่อให้ผู้ใช้รู้วิธีเริ่มต้นใช้งาน
    st.write("")
    st.markdown("""
    <div style="background-color: rgba(255, 255, 255, 0.02); padding: 1.5rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); text-align: center;">
        <span style="font-size: 1.2rem; color: #a1a1aa;">👈 กรุณาเลือกอัปโหลดไฟล์ใบเสนอราคา PDF เพื่อเริ่มระบบ</span>
    </div>
    """, unsafe_allow_html=True)