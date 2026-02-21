import api from './client'

export async function downloadClashProfile(
  userId: string,
  strategy: string = 'url-test',
  serverIds: string[] | 'all' = 'all',
) {
  const servers = serverIds === 'all' ? 'all' : serverIds.join(',')
  const response = await api.get(`/profiles/${userId}/clash`, {
    params: { strategy, servers },
    responseType: 'blob',
  })

  const disposition = response.headers['content-disposition']
  let filename = `profile-${strategy}.yaml`
  if (disposition) {
    const match = disposition.match(/filename="?([^"]+)"?/)
    if (match) filename = match[1]
  }

  const url = window.URL.createObjectURL(new Blob([response.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}
