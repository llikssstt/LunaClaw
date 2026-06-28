<template>
  <main class="app-shell">
    <section class="stage">
      <StatusPanel :status="status" />
    </section>

    <section class="workspace">
      <ChatBox :messages="messages" :loading="loading" @send="handleSend" @upload-image="handleUploadImage" />
    </section>

    <aside class="side-panels">
      <AgentFlowPanel :steps="agentFlow" />
      <PermissionReviewPanel
        :approval="pendingApproval"
        @approve="handleApproveTool"
        @reject="handleRejectTool"
      />
      <ToolStorePanel
        :market="marketTools"
        :installed="installedTools"
        @refresh="loadPanels"
        @search="handleSearchTools"
        @install="handleInstallTool"
        @enable="handleEnableTool"
        @disable="handleDisableTool"
      />
      <TaskPanel
        :tasks="tasks"
        @refresh="loadPanels"
        @run-next="handleRunTaskNext"
        @run-loop="handleRunTaskLoop"
        @pause="handlePauseTask"
        @resume="handleResumeTask"
        @cancel="handleCancelTask"
        @retry-step="handleRetryTaskStep"
      />
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
        @read-resource="handleReadSkillResource"
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
  disableTool,
  disableSkill,
  enableTool,
  enableSkill,
  approveTool,
  cancelTask,
  fetchTools,
  fetchEvolutionLogs,
  fetchEvolutionSkills,
  fetchMemory,
  fetchSkills,
  fetchTasks,
  fetchTodos,
  installSkill,
  installTool,
  readSkill,
  readSkillResource,
  rollbackEvolution,
  pauseTask,
  resumeTask,
  retryTaskStep,
  runTaskNext,
  runTaskUntilIdle,
  searchTools,
  sendChat,
  uploadImage
} from './api/chat'
import AgentFlowPanel from './components/AgentFlowPanel.vue'
import ChatBox from './components/ChatBox.vue'
import EvolutionPanel from './components/EvolutionPanel.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import PermissionReviewPanel from './components/PermissionReviewPanel.vue'
import SkillManagerPanel from './components/SkillManagerPanel.vue'
import StatusPanel from './components/StatusPanel.vue'
import TaskPanel from './components/TaskPanel.vue'
import TodoPanel from './components/TodoPanel.vue'
import ToolStorePanel from './components/ToolStorePanel.vue'

const emptyArtifacts = () => ({
  retrieved_memories: [],
  evolution_events: [],
  active_skills: [],
  skill_trace: [],
  skill_resource_results: [],
  sources: [],
  tool_trace: [],
  agent_flow: [],
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
const marketTools = ref([])
const installedTools = ref([])
const tasks = ref([])
const agentFlow = ref([])
const pendingApproval = ref(null)
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

async function handleSend(payload) {
  const message = typeof payload === 'string' ? payload : payload.message
  const attachments = typeof payload === 'string' ? [] : payload.attachments || []
  messages.value.push({ role: 'user', content: message, attachments, ...emptyArtifacts() })
  loading.value = true
  try {
    const result = await sendChat(message, 'default', attachments)
    agentFlow.value = result.agent_flow || []
    if (result.approval_required) {
      pendingApproval.value = {
        approval_id: result.approval_id,
        security_review: result.security_review,
        tool: (result.candidate_tools || [])[0]
      }
    }
    messages.value.push({
      role: 'assistant',
      content: result.reply,
      retrieved_memories: result.retrieved_memories || [],
      evolution_events: result.evolution_events || [],
      active_skills: result.active_skills || [],
      skill_trace: result.skill_trace || [],
      skill_resource_results: result.skill_resource_results || [],
      sources: result.sources || [],
      tool_trace: result.tool_trace || [],
      agent_flow: result.agent_flow || [],
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
    const [memoryData, todoData, logData, evolutionSkillData, installedSkillData, toolData, taskData] = await Promise.all([
      fetchMemory(),
      fetchTodos(),
      fetchEvolutionLogs(),
      fetchEvolutionSkills(),
      fetchSkills(),
      fetchTools(),
      fetchTasks()
    ])
    memories.value = memoryData
    todos.value = todoData
    evolutionLogs.value = logData
    evolutionSkills.value = evolutionSkillData
    installedSkills.value = installedSkillData.skills || []
    marketTools.value = toolData.market || []
    installedTools.value = toolData.installed || []
    tasks.value = taskData.tasks || []
  } catch {
    memories.value = memories.value
    todos.value = todos.value
    evolutionLogs.value = evolutionLogs.value
    evolutionSkills.value = evolutionSkills.value
    installedSkills.value = installedSkills.value
    tasks.value = tasks.value
  }
}

async function handleUploadImage(payload) {
  const result = await uploadImage(payload.file)
  payload.onSuccess?.(result)
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

async function handleSearchTools(query) {
  const result = await searchTools(query)
  marketTools.value = result.tools || []
}

async function handleInstallTool(tool) {
  const result = await installTool({ tool_id: tool.tool_id, source: tool.install_source || tool.source || 'market' })
  if (result.approval_required) {
    pendingApproval.value = {
      approval_id: result.approval_id,
      security_review: result.security_review,
      tool
    }
  } else {
    pendingApproval.value = null
    await loadPanels()
  }
}

async function handleApproveTool(approvalId) {
  const result = await approveTool(approvalId, true)
  if (result.agent_flow) agentFlow.value = result.agent_flow
  pendingApproval.value = null
  await loadPanels()
}

async function handleRejectTool(approvalId) {
  const result = await approveTool(approvalId, false)
  if (result.agent_flow) agentFlow.value = result.agent_flow
  pendingApproval.value = null
  await loadPanels()
}

async function handleEnableTool(tool) {
  await enableTool(tool.tool_id)
  await loadPanels()
}

async function handleDisableTool(tool) {
  await disableTool(tool.tool_id)
  await loadPanels()
}

async function handleRunTaskNext(task) {
  await runTaskNext(task.task_id)
  await loadPanels()
}

async function handleRunTaskLoop(task) {
  await runTaskUntilIdle(task.task_id, 5)
  await loadPanels()
}

async function handlePauseTask(task) {
  await pauseTask(task.task_id)
  await loadPanels()
}

async function handleResumeTask(task) {
  await resumeTask(task.task_id)
  await loadPanels()
}

async function handleCancelTask(task) {
  await cancelTask(task.task_id)
  await loadPanels()
}

async function handleRetryTaskStep(payload) {
  await retryTaskStep(payload.task.task_id, payload.step.step_id)
  await loadPanels()
}

async function handleViewSkill(payload) {
  try {
    const result = await readSkill(payload.skill_id)
    payload.onSuccess?.(result.skill || result)
  } catch (error) {
    payload.onError?.(error)
  }
}

async function handleReadSkillResource(payload) {
  try {
    const result = await readSkillResource(payload.skill_id, payload.resource_path)
    payload.onSuccess?.(result)
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
