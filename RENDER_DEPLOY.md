# ==========================================
# Render.com Deployment Guide
# Mango Auto Contract Generator
# ==========================================

## โครงสร้างที่ Deploy

โปรเจกต์นี้แบ่งเป็น **2 Services** บน Render:

| Service | ไฟล์ | Type | URL |
|---------|------|------|-----|
| Backend | `back_end.py` | Web Service (FastAPI) | `https://mango-backend.onrender.com` |
| Frontend | `front_end.py` | Web Service (Streamlit) | `https://mango-frontend.onrender.com` |

---

## 1. Deploy Backend (FastAPI)

### ขั้นตอน:
1. ไปที่ [render.com](https://render.com) → **New** → **Web Service**
2. เชื่อมต่อ GitHub Repository
3. ตั้งค่าดังนี้:

| ฟิลด์ | ค่าที่ต้องใส่ |
|-------|-------------|
| **Name** | `mango-backend` |
| **Environment** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn back_end:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Starter` ขึ้นไป (แนะนำ Standard เพราะใช้ Gemini ซึ่งหนัก) |

### Environment Variables ที่ต้องตั้ง:
| Key | Value |
|-----|-------|
| `GEMINI_API_KEY` | `your-gemini-api-key-here` |

---

## 2. Deploy Frontend (Streamlit)

### ขั้นตอน:
1. **New** → **Web Service** อีกอัน
2. ใช้ Repository เดิม
3. ตั้งค่าดังนี้:

| ฟิลด์ | ค่าที่ต้องใส่ |
|-------|-------------|
| **Name** | `mango-frontend` |
| **Environment** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `streamlit run front_end.py --server.port $PORT --server.address 0.0.0.0` |
| **Instance Type** | `Free` หรือ `Starter` |

### Environment Variables ที่ต้องตั้ง:
| Key | Value |
|-----|-------|
| `BACKEND_URL` | `https://mango-backend.onrender.com/generate-contract` |

---

## 3. ไฟล์ที่ต้องมีใน Repository

```
Fill_From_Deploy/
├── back_end.py          ✅ FastAPI backend
├── front_end.py         ✅ Streamlit frontend
├── template.docx        ✅ เทมเพลต Word (ต้อง push ขึ้น Git ด้วย!)
├── requirements.txt     ✅ Dependencies
├── Procfile             ✅ Start command (optional แต่แนะนำ)
├── render.yaml          ✅ Infrastructure as Code (optional)
└── .env                 ❌ ห้าม push ขึ้น Git! (ใส่ใน .gitignore)
```

> ⚠️ **สำคัญมาก**: ไฟล์ `template.docx` **ต้องอยู่ใน Repository** เพราะ `back_end.py` อ่านไฟล์นี้ตรงๆ

---

## 4. ไฟล์ .gitignore ที่แนะนำ

```
.env
__pycache__/
temp_files/
*.pdf
*.docx
!template.docx
gemini_analysis.json
ocr_result.json
```

---

## 5. หมายเหตุสำคัญ

- **Free Tier Render**: Service จะ sleep หลังจากไม่มีการใช้งาน 15 นาที → ครั้งแรกที่เรียกจะช้า
- **Timeout**: Gemini ใช้เวลานาน ให้ตั้ง timeout ของ Streamlit client ไว้ที่ 180 วินาที (ตั้งไว้แล้วในโค้ด)
- **temp_files**: Render ใช้ ephemeral storage → ไฟล์ temp ถูกลบได้ตลอดเวลา (โค้ดปัจจุบันลบเองอยู่แล้ว ✅)
