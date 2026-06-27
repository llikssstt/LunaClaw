<template>
  <section class="panel skill-manager-panel">
    <div class="panel-title">
      <div>
        <h2>Skill Manager</h2>
        <small>{{ skills.length }} installed</small>
      </div>
      <button @click="$emit('refresh')">Refresh</button>
    </div>

    <form class="skill-install-form" @submit.prevent="handleInstall">
      <input v-model="url" placeholder="Skill markdown or GitHub URL" />
      <input v-model="skillId" placeholder="Optional skill_id / pack_id" />
      <button :disabled="installing || !url.trim()">{{ installing ? 'Installing' : 'Install' }}</button>
      <small v-if="message" :class="{ error: hasError }">{{ message }}</small>
    </form>

    <article v-if="selectedSkill" class="skill-detail">
      <div class="panel-title">
        <div>
          <h3>{{ selectedSkill.name || selectedSkill.skill_id }}</h3>
          <small>{{ selectedSkill.skill_id }}</small>
        </div>
        <button @click="selectedSkill = null">Close</button>
      </div>
      <p>{{ selectedSkill.description || 'No description' }}</p>
      <details open>
        <summary>SKILL.md</summary>
        <pre>{{ selectedSkill.content }}</pre>
      </details>
      <details>
        <summary>Resources</summary>
        <ul class="compact-list">
          <li v-for="resource in selectedSkill.resources || []" :key="resource">
            <small>{{ resource }}</small>
          </li>
        </ul>
        <p v-if="!(selectedSkill.resources && selectedSkill.resources.length)" class="empty">No resources.</p>
      </details>
    </article>

    <ul v-if="skills.length" class="compact-list skill-list">
      <li v-for="skill in skills" :key="skill.path || skill.skill_id">
        <strong>{{ skill.name || skill.skill_id }}</strong>
        <small>{{ skill.description || 'No description' }}</small>
        <div v-if="skill.triggers && skill.triggers.length" class="tag-row">
          <small v-for="trigger in skill.triggers.slice(0, 8)" :key="trigger">{{ trigger }}</small>
        </div>
        <small>{{ skill.enabled === false ? 'disabled' : 'enabled' }}</small>
        <div class="skill-actions">
          <button @click="handleView(skill)">View</button>
          <button v-if="skill.enabled === false" @click="handleEnable(skill)">Enable</button>
          <button v-else @click="handleDisable(skill)">Disable</button>
          <button :disabled="skill.delete_allowed === false" @click="handleDelete(skill)">Delete</button>
        </div>
      </li>
    </ul>
    <p v-else class="empty">No skills loaded.</p>
  </section>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  skills: { type: Array, default: () => [] },
  installing: { type: Boolean, default: false }
})

const emit = defineEmits(['install', 'refresh', 'view', 'enable', 'disable', 'delete'])

const url = ref('https://github.com/Yuan1z0825/nature-skills')
const skillId = ref('nature_skills')
const message = ref('')
const hasError = ref(false)
const selectedSkill = ref(null)

function handleInstall() {
  message.value = ''
  hasError.value = false
  emit('install', {
    url: url.value.trim(),
    skill_id: skillId.value.trim() || undefined,
    onSuccess: (result) => {
      if (result.mode === 'pack') {
        message.value = `Installed ${result.installed_count} skills, ${result.failed_count} failed`
      } else {
        message.value = `Installed ${result.skill_id || result.name || 'skill'}`
      }
      hasError.value = false
    },
    onError: showError
  })
}

function handleView(skill) {
  emit('view', {
    skill_id: skill.skill_id,
    onSuccess: (result) => {
      selectedSkill.value = result
      message.value = ''
      hasError.value = false
    },
    onError: showError
  })
}

function handleEnable(skill) {
  emit('enable', {
    skill_id: skill.skill_id,
    onSuccess: () => {
      message.value = `Enabled ${skill.skill_id}`
      hasError.value = false
    },
    onError: showError
  })
}

function handleDisable(skill) {
  emit('disable', {
    skill_id: skill.skill_id,
    onSuccess: () => {
      message.value = `Disabled ${skill.skill_id}`
      hasError.value = false
    },
    onError: showError
  })
}

function handleDelete(skill) {
  emit('delete', {
    skill_id: skill.skill_id,
    onSuccess: () => {
      if (selectedSkill.value?.skill_id === skill.skill_id) selectedSkill.value = null
      message.value = `Deleted ${skill.skill_id}`
      hasError.value = false
    },
    onError: showError
  })
}

function showError(error) {
  message.value = error?.message || 'Operation failed'
  hasError.value = true
}
</script>
