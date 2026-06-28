<template>
  <section class="panel tool-store-panel">
    <div class="panel-title">
      <div>
        <h2>Tool Store</h2>
        <small>{{ installed.length }} installed / {{ market.length }} market</small>
      </div>
      <button @click="$emit('refresh')">Refresh</button>
    </div>
    <form class="skill-install-form" @submit.prevent="$emit('search', query)">
      <input v-model="query" placeholder="Search tools" />
      <button>Search</button>
    </form>

    <h3>Market</h3>
    <ul v-if="market.length" class="compact-list">
      <li v-for="tool in market" :key="tool.tool_id">
        <strong>{{ tool.name || tool.tool_id }}</strong>
        <small>{{ tool.description }}</small>
        <small>{{ tool.version }} · {{ tool.tool_id }}</small>
        <div class="skill-actions">
          <button @click="$emit('install', tool)">Install</button>
        </div>
      </li>
    </ul>

    <h3>Installed</h3>
    <ul v-if="installed.length" class="compact-list">
      <li v-for="tool in installed" :key="tool.tool_id">
        <strong>{{ tool.name || tool.tool_id }}</strong>
        <small>{{ tool.enabled === false ? 'disabled' : 'enabled' }} · {{ tool.version }}</small>
        <pre>{{ formatJson(tool.permissions || {}) }}</pre>
        <div class="skill-actions">
          <button v-if="tool.enabled === false" @click="$emit('enable', tool)">Enable</button>
          <button v-else @click="$emit('disable', tool)">Disable</button>
        </div>
      </li>
    </ul>
    <p v-if="!market.length && !installed.length" class="empty">No tools loaded.</p>
  </section>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  market: { type: Array, default: () => [] },
  installed: { type: Array, default: () => [] }
})

defineEmits(['refresh', 'search', 'install', 'enable', 'disable'])

const query = ref('web reader')

function formatJson(value) {
  return JSON.stringify(value || {}, null, 2)
}
</script>

