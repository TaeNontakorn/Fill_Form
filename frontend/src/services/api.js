import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 180000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_info')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export async function login(userid, userpass) {
  const { data } = await api.post('/login', { userid, userpass })
  return data
}

export async function getQuotation(quotationId) {
  const { data } = await api.get(`/quotation/${quotationId}`)
  return data
}

export async function generateContract(quotationId, resultQuotation) {
  const { data } = await api.post('/generate-contract', {
    quotation_id: quotationId,
    result_quotation: resultQuotation,
  })
  return data
}

export default api
