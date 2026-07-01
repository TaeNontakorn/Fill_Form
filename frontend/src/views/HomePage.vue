<template>
  <div class="home-wrapper">
    <!-- Sidebar -->
    <Transition name="slide">
      <aside v-if="sidebarOpen" class="sidebar">
        <div class="sidebar-content">
          <h3>&#x1F464; ข้อมูลผู้ใช้</h3>
          <p class="user-name">{{ auth.user?.userid || 'ผู้ใช้งาน' }}</p>
          <hr />
          <button class="btn-logout" @click="handleLogout">
            &#x1F6AA; ออกจากระบบ
          </button>
        </div>
      </aside>
    </Transition>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Top bar -->
      <div class="top-bar">
        <button class="btn-menu" @click="sidebarOpen = !sidebarOpen">
          &#9776;
        </button>
        <div class="user-badge">
          <div class="user-avatar">
            {{ (auth.user?.userid || 'U')[0].toUpperCase() }}
          </div>
          <span>{{ auth.user?.userid || 'ผู้ใช้งาน' }}</span>
        </div>
      </div>

      <!-- Header -->
      <div class="header-container">
        <h1 class="main-title">Mango Auto Contract Generator</h1>
        <p class="subtitle">
          ระบบวิเคราะห์ใบเสนอราคาและออกสัญญาจัดซื้ออัตโนมัติ
        </p>
        <div class="steps-row">
          <div class="step-card">
            <div class="step-icon">&#x1F4E4;</div>
            <div class="step-title">1. เลือกเลขที่ใบเสนอราคา</div>
          </div>
          <div class="step-card">
            <div class="step-icon">&#x1F9E0;</div>
            <div class="step-title">2. AI สกัดและวิเคราะห์</div>
          </div>
          <div class="step-card">
            <div class="step-icon">&#x1F4E5;</div>
            <div class="step-title">3. ดาวน์โหลดสัญญา</div>
          </div>
        </div>
      </div>

      <!-- Form Section -->
      <div class="form-section">
        <h2>กรุณากรอกเลขที่ใบเสนอราคา</h2>
        <div class="input-row">
          <input
            v-model="quotationId"
            type="text"
            placeholder="เช่น QO2603TRA001"
            :disabled="processing"
            @keyup.enter="handleSubmit"
          />
          <button
            class="btn-submit"
            :disabled="!quotationId.trim() || processing"
            @click="handleSubmit"
          >
            <span v-if="!processing">&#x2705; ยืนยัน</span>
            <span v-else class="spinner"></span>
          </button>
        </div>

        <!-- DBD Upload -->
        <div class="dbd-upload-row">
          <label class="dbd-label" for="dbd-file">
            &#x1F4C4; แนบหนังสือรับรองบริษัท (DBD) <span class="optional-tag">ไม่บังคับ</span>
          </label>
          <div class="dbd-input-wrap">
            <input
              id="dbd-file"
              type="file"
              accept=".pdf"
              :disabled="processing"
              @change="onDbdFileChange"
              class="dbd-file-input"
            />
            <label for="dbd-file" class="dbd-file-display">
              <span v-if="dbdFile">&#x2705; {{ dbdFile.name }}</span>
              <span v-else class="placeholder-text">เลือกไฟล์ PDF...</span>
            </label>
            <button v-if="dbdFile" class="btn-clear-dbd" @click="dbdFile = null" title="ลบไฟล์">&#x2715;</button>
          </div>
          <p v-if="dbdFile" class="dbd-hint">ระบบจะดึง เลขทะเบียน / กรรมการ / ผู้มีอำนาจลงนาม จาก PDF อัตโนมัติ</p>
        </div>
      </div>

      <!-- Status Messages -->
      <Transition name="fade">
        <div v-if="statusMsg" :class="['status-msg', statusType]">
          {{ statusMsg }}
        </div>
      </Transition>

      <!-- Progress Steps -->
      <div v-if="processing" class="progress-section">
        <div
          v-for="(step, i) in progressSteps"
          :key="i"
          :class="['progress-step', { active: currentStep >= i, done: currentStep > i }]"
        >
          <div class="progress-dot">
            <span v-if="currentStep > i">&#x2713;</span>
            <span v-else-if="currentStep === i" class="spinner-sm"></span>
            <span v-else>{{ i + 1 }}</span>
          </div>
          <span>{{ step }}</span>
        </div>
      </div>

      <!-- Download Result -->
      <Transition name="fade">
        <div v-if="downloadReady" class="result-section">
          <div class="result-card">
            <div class="result-icon">&#x2728;</div>
            <h3>สร้างสัญญาสำเร็จเรียบร้อย!</h3>
            <button class="btn-download" @click="downloadFile">
              &#x1F4E5; ดาวน์โหลดเอกสารสัญญา (Word)
            </button>
          </div>

          <!-- Contract Data Expandable -->
          <details class="data-details">
            <summary>&#x1F4CA; ข้อมูลที่สกัดได้จากใบเสนอราคา</summary>
            <div class="data-grid">
              <div
                v-for="(value, key) in contractData"
                :key="key"
                class="data-row"
              >
                <span class="data-key">{{ key }}</span>
                <span :class="['data-value', { 'not-found': value === 'ไม่พบข้อมูล' }]">
                  {{ value }}
                </span>
              </div>
            </div>
          </details>
        </div>
      </Transition>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { getQuotation, generateContract, parseDbd } from '../services/api'
import { auth } from '../stores/auth'

const router = useRouter()
const sidebarOpen = ref(false)
const quotationId = ref('')
const dbdFile = ref(null)
const processing = ref(false)
const currentStep = ref(-1)
const statusMsg = ref('')
const statusType = ref('success')
const downloadReady = ref(false)
const contractData = ref(null)
const fileBase64 = ref('')
const fileName = ref('')

const progressSteps = [
  'กำลังดึงข้อมูลใบเสนอราคา...',
  'กำลังอ่านไฟล์ DBD...',
  'AI กำลังสกัดข้อมูลและสร้างสัญญา...',
  'เสร็จสิ้น!',
]

function onDbdFileChange(e) {
  dbdFile.value = e.target.files?.[0] || null
}

function handleLogout() {
  auth.logout()
  router.push({ name: 'Login' })
}

function setStatus(msg, type = 'success') {
  statusMsg.value = msg
  statusType.value = type
}

async function handleSubmit() {
  if (!quotationId.value.trim() || processing.value) return

  processing.value = true
  downloadReady.value = false
  contractData.value = null
  statusMsg.value = ''
  currentStep.value = 0

  try {
    const quotationData = await getQuotation(quotationId.value)
    setStatus('ดึงข้อมูลใบเสนอราคาสำเร็จ!')
    currentStep.value = 1

    let dbdData = null
    if (dbdFile.value) {
      const dbdResult = await parseDbd(dbdFile.value)
      dbdData = dbdResult.dbd_data
      const found = dbdResult.fields_found || []
      setStatus(`อ่านไฟล์ DBD สำเร็จ (พบ: ${found.join(', ') || 'ไม่พบข้อมูล'})`)
    }
    currentStep.value = 2

    const result = await generateContract(quotationId.value, quotationData, dbdData)
    currentStep.value = 3

    fileBase64.value = result.file_base64
    fileName.value = result.file_name || `contract_${quotationId.value}.docx`
    contractData.value = result.contract_data || {}
    downloadReady.value = true
    setStatus('สร้างสัญญาสำเร็จเรียบร้อย!')
  } catch (err) {
    if (err.code === 'ERR_NETWORK') {
      setStatus('ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้ กรุณาเปิด Back-end API ก่อน', 'error')
    } else {
      const detail =
        err.response?.data?.detail ||
        err.response?.data?.error ||
        'เกิดข้อผิดพลาดในการดำเนินการ'
      setStatus(detail, 'error')
    }
  } finally {
    processing.value = false
  }
}

function downloadFile() {
  const byteChars = atob(fileBase64.value)
  const byteNumbers = new Uint8Array(byteChars.length)
  for (let i = 0; i < byteChars.length; i++) {
    byteNumbers[i] = byteChars.charCodeAt(i)
  }
  const blob = new Blob([byteNumbers], {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName.value
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.home-wrapper {
  min-height: 100vh;
  background: radial-gradient(circle at 50% 50%, #1e1e2f 0%, #11111b 100%);
  color: #f3f4f6;
  display: flex;
}

/* Sidebar */
.sidebar {
  width: 260px;
  min-height: 100vh;
  background: rgba(255, 255, 255, 0.03);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(10px);
  flex-shrink: 0;
}

.sidebar-content {
  padding: 2rem 1.5rem;
}

.sidebar-content h3 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
  color: #d4d4d8;
}

.user-name {
  color: #a1a1aa;
  font-size: 0.95rem;
  margin: 0;
}

.sidebar-content hr {
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  margin: 1.5rem 0;
}

.btn-logout {
  width: 100%;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.25);
  color: #fca5a5;
  padding: 0.6rem 1rem;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.btn-logout:hover {
  background: rgba(239, 68, 68, 0.25);
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(-260px);
  opacity: 0;
}

/* Main */
.main-content {
  flex: 1;
  padding: 1.5rem 2rem;
  max-width: 900px;
  margin: 0 auto;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.btn-menu {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #d4d4d8;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1.2rem;
  transition: all 0.2s;
}

.btn-menu:hover {
  background: rgba(255, 255, 255, 0.1);
}

.user-badge {
  display: flex;
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
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: white;
}

/* Header */
.header-container {
  text-align: center;
  padding: 2.5rem 1.5rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  margin-bottom: 2rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.main-title {
  background: linear-gradient(135deg, #ff7e5f 0%, #feb47b 50%, #86e3ce 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-size: 2.2rem;
  font-weight: 700;
  margin: 0 0 0.5rem;
}

.subtitle {
  color: #a1a1aa;
  font-size: 1.05rem;
  font-weight: 300;
  margin: 0;
}

.steps-row {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 1.5rem;
}

.step-card {
  flex: 1;
  max-width: 200px;
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
  font-size: 0.85rem;
  font-weight: 600;
  color: #e4e4e7;
}

/* Form */
.form-section {
  margin-bottom: 1.5rem;
}

.form-section h2 {
  font-size: 1.1rem;
  font-weight: 600;
  color: #e4e4e7;
  margin: 0 0 1rem;
}

.input-row {
  display: flex;
  gap: 12px;
}

.input-row input {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  color: #f3f4f6;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  outline: none;
  transition: all 0.3s ease;
}

.input-row input:focus {
  border-color: rgba(168, 85, 247, 0.6);
  box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.15);
}

.input-row input::placeholder {
  color: #71717a;
}

.btn-submit {
  background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
  transition: all 0.3s ease;
  white-space: nowrap;
  display: flex;
  align-items: center;
}

.btn-submit:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
}

.btn-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* DBD Upload */
.dbd-upload-row {
  margin-top: 1rem;
}

.dbd-label {
  display: block;
  font-size: 0.88rem;
  color: #a1a1aa;
  margin-bottom: 0.5rem;
}

.optional-tag {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  font-size: 0.75rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  margin-left: 0.4rem;
}

.dbd-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dbd-file-input {
  display: none;
}

.dbd-file-display {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border: 1px dashed rgba(255, 255, 255, 0.15);
  border-radius: 10px;
  padding: 0.6rem 1rem;
  font-size: 0.88rem;
  color: #d4d4d8;
  cursor: pointer;
  transition: all 0.2s;
}

.dbd-file-display:hover {
  border-color: rgba(99, 102, 241, 0.5);
  background: rgba(99, 102, 241, 0.05);
}

.placeholder-text {
  color: #52525b;
}

.btn-clear-dbd {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #fca5a5;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  flex-shrink: 0;
  transition: all 0.2s;
}

.btn-clear-dbd:hover {
  background: rgba(239, 68, 68, 0.25);
}

.dbd-hint {
  font-size: 0.78rem;
  color: #6ee7b7;
  margin: 0.4rem 0 0;
}

/* Status */
.status-msg {
  padding: 0.75rem 1rem;
  border-radius: 10px;
  font-size: 0.95rem;
  margin-bottom: 1rem;
}

.status-msg.success {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #6ee7b7;
}

.status-msg.error {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
}

/* Progress */
.progress-section {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  padding: 1rem 1.5rem;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.progress-step {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #52525b;
  font-size: 0.85rem;
  transition: color 0.3s;
}

.progress-step.active {
  color: #d4d4d8;
}

.progress-step.done {
  color: #6ee7b7;
}

.progress-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}

.progress-step.done .progress-dot {
  background: rgba(16, 185, 129, 0.2);
}

.progress-step.active .progress-dot {
  background: rgba(99, 102, 241, 0.2);
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: #a855f7;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Result */
.result-section {
  margin-top: 1rem;
}

.result-card {
  text-align: center;
  padding: 2rem;
  background: rgba(16, 185, 129, 0.06);
  border: 1px solid rgba(16, 185, 129, 0.15);
  border-radius: 16px;
  margin-bottom: 1rem;
}

.result-icon {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.result-card h3 {
  color: #6ee7b7;
  font-size: 1.2rem;
  margin: 0 0 1.5rem;
}

.btn-download {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border: none;
  padding: 0.75rem 2rem;
  border-radius: 12px;
  font-size: 1.05rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
  transition: all 0.3s ease;
}

.btn-download:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(16, 185, 129, 0.6);
}

/* Data Details */
.data-details {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  overflow: hidden;
}

.data-details summary {
  padding: 1rem 1.5rem;
  cursor: pointer;
  font-weight: 600;
  color: #e4e4e7;
  font-size: 0.95rem;
  user-select: none;
}

.data-details summary:hover {
  background: rgba(255, 255, 255, 0.02);
}

.data-grid {
  padding: 0 1.5rem 1.5rem;
}

.data-row {
  display: flex;
  gap: 0.5rem;
  padding: 0.4rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 0.88rem;
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

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
