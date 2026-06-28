<template>
  <section class="panel agent-flow-panel">
    <div class="panel-title">
      <div>
        <h2>Agent Flow</h2>
        <small>{{ steps.length }} steps</small>
      </div>
    </div>
    <ol v-if="steps.length" class="flow-list">
      <li v-for="step in steps" :key="step.timestamp || step.agent_name + step.action">
        <strong>{{ step.agent_name }}</strong>
        <small>{{ step.action }} · {{ step.status }}</small>
        <p v-if="step.reason">{{ step.reason }}</p>
      </li>
    </ol>
    <p v-else class="empty">No agent flow yet.</p>
  </section>
</template>

<script setup>
defineProps({
  steps: { type: Array, default: () => [] }
})
</script>

