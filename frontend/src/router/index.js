import { createRouter, createWebHistory } from 'vue-router'
import { auth } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/LoginPage.vue'),
      beforeEnter: () => {
        if (auth.isAuthenticated) return { name: 'Home' }
      },
    },
    {
      path: '/',
      name: 'Home',
      component: () => import('../views/HomePage.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'Login' }
  }
})

export default router
