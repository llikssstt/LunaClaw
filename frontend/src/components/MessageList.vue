<template>
  <div class="message-list">
    <article v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
      <span>{{ message.role === 'user' ? 'You' : 'LunaClaw' }}</span>
      <p>{{ message.content }}</p>

      <div v-if="message.retrieved_memories && message.retrieved_memories.length" class="memory-used">
        <small>Memory used</small>
        <small v-for="memory in message.retrieved_memories" :key="memory.memory_id">
          {{ memory.category }} / {{ memory.memory_id }}
        </small>
      </div>

      <div v-if="message.evolution_summary || (message.evolution_events && message.evolution_events.length)" class="evolution-used">
        <small>Evolution</small>
        <small v-if="message.evolution_summary">{{ message.evolution_summary }}</small>
        <small v-for="event in message.evolution_events" :key="event.operation_id || event.timestamp">
          {{ event.operation }} / {{ event.target_type }}
        </small>
      </div>

      <div v-if="message.active_skills && message.active_skills.length" class="skill-used">
        <small>Loaded Skill</small>
        <small v-for="skill in message.active_skills" :key="skill.skill_id || skill.name">{{ skill.name }}</small>
      </div>

      <div
        v-if="hasSources(message) || hasToolTrace(message) || hasActiveSkills(message)"
        class="chat-artifacts"
      >
        <details v-if="hasSources(message)">
          <summary>Sources</summary>
          <ul class="artifact-list">
            <li v-for="source in message.sources" :key="source.url || source.title">
              <a v-if="source.url" :href="source.url" target="_blank" rel="noreferrer">{{ source.title || source.url }}</a>
              <strong v-else>{{ source.title || 'Untitled source' }}</strong>
              <small>{{ source.source || 'web' }}</small>
              <p v-if="source.snippet">{{ source.snippet }}</p>
            </li>
          </ul>
        </details>

        <details v-if="hasToolTrace(message)">
          <summary>Tool Trace</summary>
          <ul class="artifact-list">
            <li v-for="trace in message.tool_trace" :key="trace.step">
              <strong>Step {{ trace.step }} · {{ trace.tool_call?.name || 'none' }}</strong>
              <small>ok: {{ trace.tool_result?.ok === false ? 'false' : 'true' }}</small>
              <pre v-if="trace.tool_call?.arguments">{{ formatJson(trace.tool_call.arguments) }}</pre>
            </li>
          </ul>
        </details>

        <details v-if="hasActiveSkills(message)">
          <summary>Active Skills</summary>
          <ul class="artifact-list">
            <li v-for="skill in message.active_skills" :key="skill.skill_id || skill.name">
              <strong>{{ skill.name || skill.skill_id }}</strong>
              <small>{{ skill.description || 'No description' }}</small>
              <div v-if="skill.triggers && skill.triggers.length" class="tag-row">
                <small v-for="trigger in skill.triggers.slice(0, 8)" :key="trigger">{{ trigger }}</small>
              </div>
            </li>
          </ul>
        </details>
      </div>
    </article>
    <article v-if="loading" class="message assistant">
      <span>LunaClaw</span>
      <p>Thinking, retrieving memory, loading Skills, and preparing a response...</p>
    </article>
  </div>
</template>

<script setup>
defineProps({
  messages: { type: Array, required: true },
  loading: { type: Boolean, default: false }
})

function hasSources(message) {
  return Array.isArray(message.sources) && message.sources.length > 0
}

function hasToolTrace(message) {
  return Array.isArray(message.tool_trace) && message.tool_trace.length > 0
}

function hasActiveSkills(message) {
  return Array.isArray(message.active_skills) && message.active_skills.length > 0
}

function formatJson(value) {
  return JSON.stringify(value || {}, null, 2)
}
</script>
