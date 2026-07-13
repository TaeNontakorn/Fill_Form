# ระบบ Authentication — Fill_Form (Mango Contract Generation)

> สรุปจากโค้ดจริง: `back_end.py`, `frontend/src/stores/auth.js`, `frontend/src/services/api.js`,
> `frontend/src/views/LoginPage.vue`, `frontend/src/router/index.js`

## ภาพรวม

ระบบนี้ **ไม่มีฐานข้อมูลผู้ใช้ของตัวเอง** — การยืนยันตัวตนทั้งหมดฝากไว้กับ
**Mango Anywhere API** (ระบบภายนอก) โดย Backend (FastAPI) ทำหน้าที่เป็นตัวกลาง (proxy) เท่านั้น

```
[Browser / Vue] ──► [FastAPI back_end.py] ──► [Mango Anywhere API]
   localStorage         proxy /login              /api/public/Login
   Bearer token         ส่งต่อ token               X-Mango-Auth
```

## การตั้งค่า (Environment Variables)

| ตัวแปร | ค่า default | ใช้ทำอะไร |
|---|---|---|
| `EXTERNAL_AUTH_LOGIN_URL` | `https://service.mangoanywhere.com/api/public/Login` | endpoint ล็อกอินภายนอก |
| `MAINCODE` | `MANGO` | รหัสบริษัทที่แนบไปตอนล็อกอิน |
| `EXTERNAL_QUOTATION_URL` | `https://service.mangoanywhere.com/Anywhere/BD/QO_ReadData` | ดึงใบเสนอราคา + ใช้ตรวจว่า token ยังใช้ได้ |

(อ้างอิง `back_end.py` บรรทัด ~37–47)

## ขั้นตอนที่ 1: Login

### ฝั่งผู้ใช้ (LoginPage.vue)
1. ผู้ใช้กรอก **User ID** และ **Password** ที่หน้า `/login`
2. กดปุ่ม "เข้าสู่ระบบ" → เรียก `login(userid, userpass)` จาก `services/api.js`

### ฝั่ง Backend (`POST /login` — back_end.py:672)
3. FastAPI รับ `{ userid, userpass }` (Pydantic model `LoginRequest`)
4. ส่งต่อไปยัง Mango Anywhere ด้วย body:
   ```json
   { "maincode": "MANGO", "userid": "...", "userpass": "..." }
   ```
   (timeout 300 วินาที)
5. ถ้า external ตอบ 200:
   - อ่าน `result.success` — ถ้า `true` ล็อกสำเร็จ, ถ้า `false` มี `result.error` บอกสาเหตุ
   - ส่ง response ทั้งก้อนกลับไปให้ frontend ตรง ๆ
6. ถ้าไม่ใช่ 200 → โยน `HTTPException` พร้อมข้อความ "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
7. ถ้าเชื่อมต่อไม่ได้ → 503 "ไม่สามารถเชื่อมต่อกับระบบยืนยันตัวตนภายนอกได้"

### ฝั่ง Frontend รับผลลัพธ์ (LoginPage.vue:91–100)
8. ถ้า `result.success === true` → **token อยู่ใน `result.data`**
9. เรียก `auth.setLogin(token, { userid })` ซึ่งเก็บลง `localStorage`:
   - `auth_token` = token
   - `user_info` = `{ "userid": "..." }`
10. redirect ไปหน้า Home (`/`)

## ขั้นตอนที่ 2: การใช้ Token เรียก API

ทุก request หลังล็อกอินจะแนบ token อัตโนมัติผ่าน **axios interceptor**
(`services/api.js:8–14`):

```
Authorization: Bearer <token>
```

Backend endpoint ที่ต้องมี token (ทุกตัวเช็คแบบเดียวกัน):

| Endpoint | Method | หน้าที่ |
|---|---|---|
| `/quotation/{quotation_id}` | GET | ดึงใบเสนอราคาจาก Mango Anywhere |
| `/parse-dbd` | POST | อัปโหลด PDF หนังสือรับรอง DBD |
| `/generate-contract` | POST | สร้างสัญญาด้วย Gemini |

การเช็คในแต่ละ endpoint:
1. อ่าน header `Authorization` — ถ้าไม่มี หรือไม่ขึ้นต้นด้วย `Bearer ` → **401** "กรุณาเข้าสู่ระบบก่อนใช้งาน"
2. ตัดคำว่า `Bearer ` ออก เหลือ token
3. เวลาเรียก API ภายนอก จะส่ง token ต่อในรูป header **`X-Mango-Auth: <token>`**
   (เช่น `/quotation/{id}` ที่ back_end.py:732–736)

> หมายเหตุ: `/parse-dbd` และ `/generate-contract` เช็คแค่ว่า "มี Bearer token"
> แต่**ไม่ได้ตรวจกับระบบภายนอกว่า token ยังใช้ได้จริง** — token ปลอมหรือหมดอายุก็ผ่านสองตัวนี้ได้

## ขั้นตอนที่ 3: ตรวจสอบ Token (verify_token — back_end.py:707)

มีฟังก์ชัน `verify_token` ที่ตรวจ token กับระบบภายนอก โดยยิง GET ไปที่
`EXTERNAL_QUOTATION_URL` พร้อม header `X-Mango-Auth`:
- ตอบ 200 → token ใช้ได้
- อื่น ๆ → 401 "Token หมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่"

> ปัจจุบันฟังก์ชันนี้**ยังไม่ได้ถูกใช้เป็น `Depends()` ใน endpoint ไหนเลย** —
> ประกาศไว้เฉย ๆ (dead code) ถ้าต้องการให้ทุก endpoint ตรวจ token จริง
> ต้องเติม `Depends(verify_token)` เข้าไป

## ขั้นตอนที่ 4: การป้องกันหน้าเว็บ (Router Guard)

`frontend/src/router/index.js`:
- หน้า `/` (Home) มี `meta: { requiresAuth: true }` — ถ้าไม่มี token ใน store → เด้งไป `/login`
- หน้า `/login` — ถ้าล็อกอินอยู่แล้ว → เด้งกลับ Home
- การเช็ค `isAuthenticated` = แค่ดูว่ามี `auth_token` ใน localStorage (ไม่เช็คหมดอายุฝั่ง client)

## ขั้นตอนที่ 5: Token หมดอายุ / Logout

- **หมดอายุอัตโนมัติ**: axios response interceptor (`api.js:16–26`) —
  ถ้า API ไหนตอบ **401** จะลบ `auth_token` + `user_info` ออกจาก localStorage
  แล้ว redirect ไป `/login` ทันที
- **Logout เอง**: เรียก `auth.logout()` — ลบ token/user ออกจาก store และ localStorage

## สรุป Flow ทั้งหมดในรูปเดียว

```
1. ผู้ใช้กรอก userid/userpass ที่ /login
2. Frontend → POST /login (FastAPI)
3. FastAPI → POST Mango Anywhere /api/public/Login  { maincode, userid, userpass }
4. สำเร็จ → token กลับมาใน result.data
5. Frontend เก็บ token ลง localStorage (auth_token)
6. ทุก request ต่อไป axios แนบ  Authorization: Bearer <token>
7. FastAPI ตัด token แล้วส่งต่อภายนอกเป็น  X-Mango-Auth: <token>
8. ถ้า 401 กลับมาเมื่อไร → ล้าง localStorage แล้วเด้งกลับหน้า login
```

## ข้อสังเกต / จุดที่ควรปรับปรุง

1. `verify_token` เป็น dead code — endpoint จริงเช็คแค่รูปแบบ `Bearer ` ไม่ได้ validate token
2. `/parse-dbd` และ `/generate-contract` รับ token ปลอมได้ (ไม่ตรวจกับภายนอก)
3. CORS เปิด `allow_origins=["*"]` พร้อม `allow_credentials=True` — กว้างเกินไปสำหรับ production
4. token เก็บใน localStorage — เสี่ยง XSS (ทางเลือก: httpOnly cookie)
5. ไม่มี endpoint logout ฝั่ง backend — logout เป็นเรื่องของ client ล้วน ๆ
