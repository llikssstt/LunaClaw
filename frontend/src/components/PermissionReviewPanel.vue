<template>
  <section class="panel permission-review-panel">
    <div class="panel-title">
      <div>
        <h2>Permission Review</h2>
        <small>{{ approval?.approval_id ? 'pending' : 'none' }}</small>
      </div>
    </div>
    <article v-if="approval?.approval_id" class="permission-card">
      <strong>{{ approval.tool?.name || approval.tool?.tool_id || 'Tool install' }}</strong>
      <small>approval_id: {{ approval.approval_id }}</small>
      <small>risk: {{ approval.security_review?.risk_level || 'unknown' }}</small>
      <pre>{{ formatJson(approval.security_review?.permissions || {}) }}</pre>
      <p>{{ approval.security_review?.reason }}</p>
      <div class="skill-actions">
        <button @click="$emit('approve', approval.approval_id)">Approve</button>
        <button @click="$emit('reject', approval.approval_id)">Reject</button>
      </div>
    </article>
    <p v-else class="empty">No pending approval.</p>
  </section>
</template>

<script setup>
defineProps({
  approval: { type: Object, default: null }
})

defineEmits(['approve', 'reject'])

function formatJson(value) {
  return JSON.stringify(value || {}, null, 2)
}
</script>

