<template>
  <main class="app-shell">
    <section class="stage">
      <StatusPanel :status="status" />
    </section>

    <section class="workspace">
      <ChatBox :messages="messages" :loading="loading" @send="handleSend" />
    </section>

    <aside class="side-panels">
      <EvolutionPanel
        :logs="evolutionLogs"
        :skills="evolutionSkills"
        @refresh="loadPanels"
        @rollback="handleRollbackEvolution"
      />
      <MemoryPanel
        :items="memories"
        @refresh="loadPanels"
        @delete="handleDeleteMemory"
        @create="handleCreateMemory"
      />
      <TodoPanel :items="todos" @refresh="loadPanels" />
      <SkillManagerPanel
        :skills="installedSkills"
        :installing="skillInstalling"
        @refresh="loadPanels"
        @install="handleInstallSkill"
        @view="handleViewSkill"
        @enable="handleEnableSkill"
        @disable="handleDisableSkill"
        @delete="handleDeleteSkill"
      />
    </aside>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import {
  createMemory,
  deleteMemory,
  deleteSkill,
  disableSkill,
  enableSkill,
  fetchEvolutionLogs,
  fetchEvolutionSkills,
  fetchMemory,
  fetchSkills,
  fetchTodos,
  installSkill,
  readSkill,
  rollbackEvolution,
  sendChat
} from './api/chat'
import ChatBox from './components/ChatBox.vue'
import EvolutionPanel from './components/EvolutionPanel.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import SkillManagerPanel from './components/SkillManagerPanel.vue'
import StatusPanel from './components/StatusPanel.vue'
import TodoPanel from './components/TodoPanel.vue'

const emptyArtifacts = () => ({
  retrieved_memories: [],
  evolution_events: [],
  active_skills: [],
  sources: [],
  tool_trace: [],
  evolution_summary: ''
})

const messages = ref([
  {
    role: 'assistant',
    content: 'I am LunaClaw. Ask me to search, fetch sources, use tools, load Skills, or install a Skill from a URL.',
    ...emptyArtifacts()
  }
])
const memories = ref([])
const todos = ref([])
const evolutionLogs = ref([])
const evolutionSkills = ref([])
const installedSkills = ref([])
const loading = ref(false)
const skillInstalling = ref(false)
const status = reactive({
  emotion: 'neutral',
  tool_used: 'none',
  memory_action: 'none',
  skills_used: ['persona_skill'],
  active_skills: [],
  evolution_count: 0
})

async function handleSend(text) {
  messages.value.push({ role: 'user', content: text, ...emptyArtifacts() })
  loading.value = true
  try {
    const result = await sendChat(text)
    messages.value.push({
      role: 'assistant',
      content: result.reply,
      retrieved_memories: result.retrieved_memories || [],
      evolution_events: result.evolution_events || [],
      active_skills: result.active_skills || [],
      sources: result.sources || [],
      tool_trace: result.tool_trace || [],
      evolution_summary: result.evolution_summary || ''
    })
    Object.assign(status, {
      ...result,
      active_skills: result.active_skills || [],
      evolution_count: result.evolution_count || 0
    })
    await loadPanels()
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: 'Backend is not reachable. Confirm FastAPI is running at http://127.0.0.1:8000.',
      ...emptyArtifacts()
    })
    Object.assign(status, {
      emotion: 'thinking',
      tool_used: 'none',
      memory_action: 'none',
      skills_used: ['frontend_fallback'],
      active_skills: [],
      evolution_count: 0
    })
  } finally {
    loading.value = false
  }
}

async function loadPanels() {
  try {
    const [memoryData, todoData, logData, evolutionSkillData, installedSkillData] = await Promise.all([
      fetchMemory(),
      fetchTodos(),
      fetchEvolutionLogs(),
      fetchEvolutionSkills(),
      fetchSkills()
    ])
    memories.value = memoryData
    todos.value = todoData
    evolutionLogs.value = logData
    evolutionSkills.value = evolutionSkillData
    installedSkills.value = installedSkillData.skills || []
  } catch {
    memories.value = memories.value
    todos.value = todos.value
    evolutionLogs.value = evolutionLogs.value
    evolutionSkills.value = evolutionSkills.value
    installedSkills.value = installedSkills.value
  }
}

async function handleDeleteMemory(memoryId) {
  await deleteMemory(memoryId)
  await loadPanels()
}

async function handleCreateMemory(payload) {
  await createMemory(payload)
  await loadPanels()
}

async function handleRollbackEvolution(operationId) {
  await rollbackEvolution(operationId)
  await loadPanels()
}

async function handleInstallSkill(payload) {
  skillInstalling.value = true
  try {
    const result = await installSkill({ url: payload.url, skill_id: payload.skill_id })
    payload.onSuccess?.(result)
    await loadPanels()
  } catch (error) {
    payload.onError?.(error)
  } finally {
    skillInstalling.value = false
  }
}

async function handleViewSkill(payload) {
  try {
    const result = await readSkill(payload.skill_id)
    payload.onSuccess?.(result.skill || result)
  } catch (error) {
    payload.onError?.(error)
  }
}

async function handleEnableSkill(payload) {
  try {
    await enableSkill(payload.skill_id)
    payload.onSuccess?.()
    await loadPanels()
  } catch (error) {
    payload.onError?.(error)
  }
}

async function handleDisableSkill(payload) {
  try {
    await disableSkill(payload.skill_id)
    payload.onSuccess?.()
    await loadPanels()
  } catch (error) {
    payload.onError?.(error)
  }
}

async function handleDeleteSkill(payload) {
  try {
    await deleteSkill(payload.skill_id)
    payload.onSuccess?.()
    await loadPanels()
  } catch (error) {
    payload.onError?.(error)
  }
}

onMounted(loadPanels)
</script>
