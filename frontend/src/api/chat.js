const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json()
}

export function sendChat(message, sessionId = 'default', attachments = []) {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId, attachments })
  })
}

export async function uploadImage(file) {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${API_BASE}/uploads/image`, { method: 'POST', body: form })
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}

export function fetchMemory() {
  return request('/memory')
}

export function createMemory(payload) {
  return request('/memory', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function updateMemory(memoryId, payload) {
  return request(`/memory/${memoryId}`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  })
}

export function deleteMemory(memoryId) {
  return request(`/memory/${memoryId}`, { method: 'DELETE' })
}

export function searchMemory(query) {
  return request(`/memory/search?query=${encodeURIComponent(query)}`)
}

export function fetchEvolutionLogs() {
  return request('/evolution/logs')
}

export function fetchEvolutionSkills() {
  return request('/evolution/skills')
}

export function fetchSkills() {
  return request('/skills')
}

export function installSkill(payload) {
  return request('/skills/install', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function readSkill(skillId) {
  return request(`/skills/${encodeURIComponent(skillId)}`)
}

export function fetchSkillResources(skillId) {
  return request(`/skills/${encodeURIComponent(skillId)}/resources`)
}

export function readSkillResource(skillId, resourcePath, maxChars = 8000) {
  const path = resourcePath.split('/').map(encodeURIComponent).join('/')
  return request(`/skills/${encodeURIComponent(skillId)}/resources/${path}?max_chars=${maxChars}`)
}

export function enableSkill(skillId) {
  return request(`/skills/${encodeURIComponent(skillId)}/enable`, { method: 'POST' })
}

export function disableSkill(skillId) {
  return request(`/skills/${encodeURIComponent(skillId)}/disable`, { method: 'POST' })
}

export function deleteSkill(skillId) {
  return request(`/skills/${encodeURIComponent(skillId)}`, { method: 'DELETE' })
}

export function fetchTools() {
  return request('/tools')
}

export function searchTools(query) {
  return request('/tools/search', {
    method: 'POST',
    body: JSON.stringify({ query })
  })
}

export function installTool(payload) {
  return request('/tools/install', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function approveTool(approvalId, approved) {
  return request(`/tools/approve/${encodeURIComponent(approvalId)}`, {
    method: 'POST',
    body: JSON.stringify({ approved })
  })
}

export function enableTool(toolId) {
  return request(`/tools/${encodeURIComponent(toolId)}/enable`, { method: 'POST' })
}

export function disableTool(toolId) {
  return request(`/tools/${encodeURIComponent(toolId)}/disable`, { method: 'POST' })
}

export function rollbackEvolution(operationId) {
  return request(`/evolution/rollback/${operationId}`, { method: 'POST' })
}

export function fetchTodos() {
  return request('/todos')
}
