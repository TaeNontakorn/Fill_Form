import { reactive } from 'vue'

export const auth = reactive({
  token: localStorage.getItem('auth_token') || null,
  user: JSON.parse(localStorage.getItem('user_info') || 'null'),

  get isAuthenticated() {
    return !!this.token
  },

  setLogin(token, user) {
    this.token = token
    this.user = user
    localStorage.setItem('auth_token', token)
    localStorage.setItem('user_info', JSON.stringify(user))
  },

  logout() {
    this.token = null
    this.user = null
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user_info')
  },
})
