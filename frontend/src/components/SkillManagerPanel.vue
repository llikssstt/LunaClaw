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
      <input v-model="skillId" placeholder="Optional skill_id" />
      <button :disabled="installing || !url.trim()">{{ installing ? 'Installing' : 'Install' }}</button>
      <small v-if="message" :class="{ error: hasError }">{{ message }}</small>
    </form>

    <ul v-if="skills.length" class="compact-list skill-list">
      <li v-for="skill in skills" :key="skill.path || skill.skill_id">
        <strong>{{ skill.name || skill.skill_id }}</strong>
        <small>{{ skill.description || 'No description' }}</small>
        <div v-if="skill.triggers && skill.triggers.length" class="tag-row">
          <small v-for="trigger in skill.triggers.slice(0, 8)" :key="trigger">{{ trigger }}</small>
        </div>
        <small>{{ skill.enabled === false ? 'disabled' : 'enabled' }}</small>
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

const emit = defineEmits(['install', 'refresh'])

const url = ref('https://github.com/Yuan1z0825/nature-skills')
const skillId = ref('nature_skills')
const message = ref('')
const hasError = ref(false)

function handleInstall() {
  message.value = ''
  hasError.value = false
  emit('install', {
    url: url.value.trim(),
    skill_id: skillId.value.trim() || undefined,
    onSuccess: (result) => {
      message.value = `Installed ${result.skill_id || result.name || 'skill'}`
      hasError.value = false
    },
    onError: (error) => {
      message.value = error?.message || 'Install failed'
      hasError.value = true
    }
  })
}
</script>
