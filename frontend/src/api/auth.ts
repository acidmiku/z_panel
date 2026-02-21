import api from './client'

export async function login(username: string, password: string) {
  const { data } = await api.post('/auth/login', { username, password })
  return data as { access_token: string; refresh_token: string; token_type: string }
}

export async function changePassword(currentPassword: string, newPassword: string) {
  const { data } = await api.post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
  return data
}
