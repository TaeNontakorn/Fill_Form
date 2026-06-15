from streamlit.runtime import uploaded_file_manager
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

# API Endpoint ของ FastAPI Back-end
API_BASE_URL = "http://localhost:8000"
API_LOGIN_URL = f"{API_BASE_URL}/login"
API_GENERATE_URL = f"{API_BASE_URL}/generate-contract"
API_QUOTATION_URL = f"{API_BASE_URL}/quotation"

# =================================================================
# จัดการ Session State สำหรับ Authentication
# =================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
if "user_info" not in st.session_state:
    st.session_state.user_info = None

# =================================================================
# CSS สำหรับหน้า Login (Glassmorphism สวยงามพรีเมียม)
# =================================================================
LOGIN_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Sarabun:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Sarabun', 'Outfit', sans-serif;
    }
    
    /* ซ่อนแถบเครื่องมือของ Streamlit เพื่อความสะอาดตา */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* พื้นหลังไล่เฉดสีพรีเมียม พร้อม animated gradient */
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        background-size: 400% 400%;
        animation: gradientShift 12s ease infinite;
        color: #f3f4f6;
        min-height: 100vh;
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Floating orbs สำหรับเพิ่มความสวยงาม */
    .login-bg-orb1 {
        position: fixed;
        top: -120px;
        right: -80px;
        width: 350px;
        height: 350px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(168, 85, 247, 0.25) 0%, transparent 70%);
        filter: blur(60px);
        animation: floatOrb 8s ease-in-out infinite;
        pointer-events: none;
        z-index: 0;
    }
    
    .login-bg-orb2 {
        position: fixed;
        bottom: -100px;
        left: -60px;
        width: 300px;
        height: 300px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(99, 102, 241, 0.2) 0%, transparent 70%);
        filter: blur(50px);
        animation: floatOrb 10s ease-in-out infinite reverse;
        pointer-events: none;
        z-index: 0;
    }
    
    @keyframes floatOrb {
        0%, 100% { transform: translateY(0px) scale(1); }
        50% { transform: translateY(-30px) scale(1.05); }
    }
    
    /* การ์ดล็อกอิน Glassmorphism */
    .login-card {
        max-width: 440px;
        margin: 6vh auto 0 auto;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 24px;
        padding: 3rem 2.5rem 2.5rem 2.5rem;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.05);
        position: relative;
        z-index: 1;
    }
    
    .login-logo {
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    .login-logo-icon {
        font-size: 3rem;
        display: inline-block;
        animation: pulse 2.5s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); opacity: 0.9; }
        50% { transform: scale(1.08); opacity: 1; }
    }
    
    .login-title {
        text-align: center;
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #ff7e5f 0%, #feb47b 50%, #86e3ce 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    
    .login-subtitle {
        text-align: center;
        color: #a1a1aa;
        font-size: 0.95rem;
        font-weight: 300;
        margin-bottom: 2rem;
    }
    
    /* สไตล์สำหรับ input fields ใน Streamlit */
    .stTextInput > div > div > input {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 12px !important;
        color: #f3f4f6 !important;
        padding: 0.75rem 1rem !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: rgba(168, 85, 247, 0.6) !important;
        box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.15) !important;
    }
    
    .stTextInput > div > div > input::placeholder {
        color: #71717a !important;
    }
    
    .stTextInput > label {
        color: #d4d4d8 !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
    }
    
    /* ปุ่ม Login ไล่สีสว่าง */
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.8rem 2rem !important;
        border-radius: 12px !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4) !important;
        transition: all 0.3s ease !important;
        margin-top: 0.5rem !important;
        letter-spacing: 0.5px !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6) !important;
        background: linear-gradient(135deg, #4f46e5 0%, #9333ea 100%) !important;
    }
    
    /* Footer ด้านล่างการ์ด */
    .login-footer {
        text-align: center;
        margin-top: 2rem;
        padding-top: 1.5rem;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        color: #71717a;
        font-size: 0.8rem;
    }
    
    .login-footer a {
        color: #a78bfa;
        text-decoration: none;
    }
    
    /* Security badge */
    .security-badge {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        margin-top: 1.5rem;
        color: #52525b;
        font-size: 0.78rem;
    }
</style>
"""

# =================================================================
# CSS สำหรับหน้าหลัก (หลังล็อกอิน)
# =================================================================
MAIN_CSS = """
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
    
    /* User bar ด้านบน */
    .user-bar {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 12px;
        padding: 0.6rem 0;
        margin-bottom: 0.5rem;
    }
    
    .user-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 50px;
        padding: 0.4rem 1rem;
        font-size: 0.85rem;
        color: #d4d4d8;
    }
    
    .user-avatar {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: linear-gradient(135deg, #6366f1, #a855f7);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.7rem;
        font-weight: 700;
        color: white;
    }
</style>
"""


# =================================================================
# ฟังก์ชันแสดงหน้า LOGIN
# =================================================================
def show_login_page():
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    
    # Background orbs สำหรับเพิ่มความสวยงาม
    st.markdown("""
    <div class="login-bg-orb1"></div>
    <div class="login-bg-orb2"></div>
    """, unsafe_allow_html=True)
    
    # การ์ดล็อกอิน
    st.markdown("""
    <div class="login-card">
        <div class="login-logo">
            <span class="login-logo-icon">🥭</span>
        </div>
        <div class="login-title">Mango Platform</div>
        <div class="login-subtitle">เข้าสู่ระบบเพื่อใช้งาน Auto Contract Generator</div>
    </div>
    """, unsafe_allow_html=True)
    
    # ใช้ container ของ Streamlit สำหรับฟอร์ม เพื่อให้กรอกข้อมูลได้
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("")  # spacing
        userid = st.text_input("👤 ชื่อผู้ใช้งาน (User ID)", placeholder="กรอกชื่อผู้ใช้งาน", key="login_userid")
        userpass = st.text_input("🔒 รหัสผ่าน", placeholder="กรอกรหัสผ่าน", type="password", key="login_userpass")
        
        st.write("")  # spacing
        login_clicked = st.button("เข้าสู่ระบบ 🚀", key="login_button", use_container_width=True)
        
        if login_clicked:
            if not userid or not userpass:
                st.error("❌ กรุณากรอกชื่อผู้ใช้และรหัสผ่านให้ครบถ้วน")
            else:
                with st.spinner("กำลังตรวจสอบข้อมูล..."):
                    try:
                        response = requests.post(
                            API_LOGIN_URL,
                            json={"userid": userid, "userpass": userpass},
                            timeout=30,
                        )
                        
                        # แสดง Log Response (เหมือนดู F12 Network tab)
                        with st.expander("🔍 Debug: API Response Log", expanded=False):
                            st.markdown(f"**URL:** `{API_LOGIN_URL}`")
                            st.markdown(f"**Status Code:** `{response.status_code}`")
                            try:
                                st.json(response.json())
                            except Exception:
                                st.code(response.text)
                        
                        if response.status_code == 200:
                            result = response.json()
                            # ตรวจสอบว่าล็อกอินสำเร็จจากฟิลด์ "success"
                            if result.get("success"):
                                token = result.get("data")  # Token อยู่ในฟิลด์ "data"
                                if token:
                                    st.session_state.authenticated = True
                                    st.session_state.auth_token = token
                                    st.session_state.user_info = {"userid": userid}
                                    st.success("✅ เข้าสู่ระบบสำเร็จ!")
                                    st.rerun()
                                else:
                                    st.error("❌ ไม่พบ Token ในคำตอบที่ได้รับจากระบบ")
                            else:
                                error_msg = result.get("error") or "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
                                st.error(f"❌ {error_msg}")
                        else:
                            try:
                                err = response.json()
                                detail = err.get("error") or err.get("detail") or "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
                            except Exception:
                                detail = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
                            st.error(f"❌ {detail}")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้ กรุณาเปิด Back-end API ก่อน")
                    except Exception as e:
                        st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
        
        # Security badge
        st.markdown("""
        <div class="security-badge">
            🔐 การเชื่อมต่อมีการเข้ารหัสเพื่อความปลอดภัย
        </div>
        """, unsafe_allow_html=True)


# =================================================================
# ฟังก์ชันแสดงหน้าหลัก (หลังล็อกอิน)
# =================================================================
def show_main_page():
    st.markdown(MAIN_CSS, unsafe_allow_html=True)
    
    # แถบข้อมูลผู้ใช้ด้านบนและปุ่ม Logout
    with st.sidebar:
        st.markdown("### 👤 ข้อมูลผู้ใช้")
        if st.session_state.user_info:
            # แสดงข้อมูลผู้ใช้ที่ได้จาก Token (ปรับตามโครงสร้างข้อมูลจริง)
            user_display = st.session_state.user_info.get("username") or \
                           st.session_state.user_info.get("name") or \
                           st.session_state.user_info.get("email") or \
                           "ผู้ใช้งาน"
            st.markdown(f"**{user_display}**")
        st.markdown("---")
        if st.button("🚪 ออกจากระบบ", key="logout_button", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.auth_token = None
            st.session_state.user_info = None
            st.rerun()

    # แสดงส่วนหัวของหน้าเว็บ
    st.markdown("""
    <div class="header-container">
        <div class="main-title">Mango Auto Contract Generator</div>
        <div class="subtitle">ระบบวิเคราะห์ใบเสนอราคาและออกสัญญาจัดซื้ออัตโนมัติ</div>
        <div class="steps-container">
            <div class="step-card">
                <div class="step-icon">📤</div>
                <div class="step-title">1. เลือกเลขที่ใบเสนอราคา</div>
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
    st.write("### กรุณากรอกเลขที่ใบเสนอราคา")
    quotation_id = st.text_input("เลขที่ใบเสนอราคา")

    if quotation_id:
        if st.button("ยืนยัน", type="primary", icon="✅"):
            with st.spinner("กำลังดึงข้อมูลใบเสนอราคา..."):
                try:
                    response = requests.get(
                        f"{API_QUOTATION_URL}/{quotation_id}",
                        headers={"Authorization": f"Bearer {st.session_state.auth_token}"},
                        timeout=30,
                    )

                    # แสดง Debug Log
                    with st.expander("🔍 Debug: API Response Log", expanded=False):
                        st.markdown(f"**URL:** `{API_QUOTATION_URL}/{quotation_id}`")
                        st.markdown(f"**Status Code:** `{response.status_code}`")
                        try:
                            st.json(response.json())
                        except Exception:
                            st.code(response.text)

                    if response.status_code == 200:
                        result = response.json()
                        st.success("✅ ดึงข้อมูลใบเสนอราคาสำเร็จ!")
                        st.session_state.quotation_data = result
                        
                        # สร้างสัญญาอัตโนมัติจากใบเสนอราคา
                        with st.spinner("🧠 AI กำลังสกัดข้อมูลและสร้างสัญญา..."):
                            try:
                                gen_response = requests.post(
                                    API_GENERATE_URL,
                                    json={"quotation_id": quotation_id, "result_quotation": result},
                                    headers={"Authorization": f"Bearer {st.session_state.auth_token}"},
                                    timeout=120,
                                )
                                
                                if gen_response.status_code == 200:
                                    gen_result = gen_response.json()
                                    file_base64 = gen_result.get("file_base64")
                                    file_name = gen_result.get("file_name", f"contract_{quotation_id}.docx")
                                    contract_data = gen_result.get("contract_data", {})
                                    
                                    st.success("✨ สร้างสัญญาสำเร็จเรียบร้อย!")
                                    
                                    # แสดงปุ่มดาวน์โหลด
                                    file_bytes = base64.b64decode(file_base64)
                                    st.download_button(
                                        label="📥 ดาวน์โหลดเอกสารสัญญา (Word)",
                                        data=file_bytes,
                                        file_name=file_name,
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    )
                                    
                                    # แสดงข้อมูลที่ AI สกัดได้ (Optional)
                                    with st.expander("📊 ข้อมูลที่สกัดได้จากใบเสนอราคา", expanded=False):
                                        st.json(contract_data)
                                        
                                else:
                                    st.error(f"❌ เกิดข้อผิดพลาดในการสร้างสัญญา: HTTP {gen_response.status_code}")
                            except Exception as e:
                                st.error(f"❌ เกิดข้อผิดพลาดตอนสร้างสัญญา: {str(e)}")

                    else:
                        try:
                            err = response.json()
                            detail = err.get("detail") or err.get("error") or "ไม่พบข้อมูลใบเสนอราคา"
                        except Exception:
                            detail = "ไม่พบข้อมูลใบเสนอราคา"
                        st.error(f"❌ {detail}")
                except requests.exceptions.ConnectionError:
                    st.error("❌ ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้ กรุณาเปิด Back-end API ก่อน")
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")


# =================================================================
# MAIN: แสดงหน้าตามสถานะล็อกอิน
# =================================================================
if st.session_state.authenticated and st.session_state.auth_token:
    show_main_page()
else:
    show_login_page()