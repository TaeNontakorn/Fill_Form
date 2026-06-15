<template>
  <div class="login-wrapper">
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>

    <div class="login-card">
      <div class="logo-section">
        <span class="logo-icon">&#x1F96D;</span>
        <h1 class="brand-title">Mango Platform</h1>
        <p class="brand-subtitle">
          เข้าสู่ระบบเพื่อใช้งาน Auto Contract Generator
        </p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="input-group">
          <label for="userid">&#x1F464; ชื่อผู้ใช้งาน (User ID)</label>
          <input
            id="userid"
            v-model="userid"
            type="text"
            placeholder="กรอกชื่อผู้ใช้งาน"
            :disabled="loading"
          />
        </div>

        <div class="input-group">
          <label for="userpass">&#x1F512; รหัสผ่าน</label>
          <input
            id="userpass"
            v-model="userpass"
            type="password"
            placeholder="กรอกรหัสผ่าน"
            :disabled="loading"
          />
        </div>

        <button type="submit" class="btn-login" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          <span v-else>เข้าสู่ระบบ &#x1F680;</span>
        </button>

        <Transition name="fade">
          <div v-if="error" class="error-msg">{{ error }}</div>
        </Transition>
      </form>

      <div class="security-badge">
        &#x1F510; การเชื่อมต่อมีการเข้ารหัสเพื่อความปลอดภัย
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../services/api'
import { auth } from '../stores/auth'

const router = useRouter()
const userid = ref('')
const userpass = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  if (!userid.value || !userpass.value) {
    error.value = 'กรุณากรอกชื่อผู้ใช้และรหัสผ่านให้ครบถ้วน'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const result = await login(userid.value, userpass.value)

    if (result.success) {
      const token = result.data
      if (token) {
        auth.setLogin(token, { userid: userid.value })
        router.push({ name: 'Home' })
      } else {
        error.value = 'ไม่พบ Token ในคำตอบที่ได้รับจากระบบ'
      }
    } else {
      error.value = result.error || 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง'
    }
  } catch (err) {
    if (err.code === 'ERR_NETWORK') {
      error.value = 'ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้ กรุณาเปิด Back-end API ก่อน'
    } else {
      const detail = err.response?.data?.detail || err.response?.data?.error
      error.value = detail || 'เกิดข้อผิดพลาดในการเข้าสู่ระบบ'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
  background-size: 400% 400%;
  animation: gradientShift 12s ease infinite;
  position: relative;
  overflow: hidden;
}

@keyframes gradientShift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.orb {
  position: fixed;
  border-radius: 50%;
  filter: blur(60px);
  pointer-events: none;
  z-index: 0;
}

.orb-1 {
  top: -120px;
  right: -80px;
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, rgba(168, 85, 247, 0.25) 0%, transparent 70%);
  animation: floatOrb 8s ease-in-out infinite;
}

.orb-2 {
  bottom: -100px;
  left: -60px;
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.2) 0%, transparent 70%);
  animation: floatOrb 10s ease-in-out infinite reverse;
}

@keyframes floatOrb {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-30px) scale(1.05); }
}

.login-card {
  position: relative;
  z-index: 1;
  max-width: 440px;
  width: 100%;
  margin: 0 1rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 24px;
  padding: 3rem 2.5rem 2.5rem;
  backdrop-filter: blur(20px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.logo-section {
  text-align: center;
  margin-bottom: 2rem;
}

.logo-icon {
  font-size: 3rem;
  display: inline-block;
  animation: pulse 2.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.08); opacity: 1; }
}

.brand-title {
  font-size: 1.8rem;
  font-weight: 700;
  background: linear-gradient(135deg, #ff7e5f 0%, #feb47b 50%, #86e3ce 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0.5rem 0 0.3rem;
}

.brand-subtitle {
  color: #a1a1aa;
  font-size: 0.95rem;
  font-weight: 300;
  margin: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}

.input-group label {
  display: block;
  color: #d4d4d8;
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 0.4rem;
}

.input-group input {
  width: 100%;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  color: #f3f4f6;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  transition: all 0.3s ease;
  outline: none;
  box-sizing: border-box;
}

.input-group input:focus {
  border-color: rgba(168, 85, 247, 0.6);
  box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.15);
}

.input-group input::placeholder {
  color: #71717a;
}

.btn-login {
  width: 100%;
  background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
  color: white;
  border: none;
  padding: 0.8rem 2rem;
  border-radius: 12px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
  transition: all 0.3s ease;
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.btn-login:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
  background: linear-gradient(135deg, #4f46e5 0%, #9333ea 100%);
}

.btn-login:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-msg {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  font-size: 0.9rem;
  text-align: center;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.security-badge {
  text-align: center;
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  color: #52525b;
  font-size: 0.78rem;
}
</style>
