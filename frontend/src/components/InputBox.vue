<template>
  <form class="input-box" @submit.prevent="submit">
    <textarea
      v-model="text"
      :disabled="disabled"
      rows="2"
      placeholder="Ask V-Agent to chat, install tools, read a web page, or analyze an uploaded image."
    />
    <div class="input-actions">
      <ImageUpload :disabled="disabled" @upload="handleUpload" />
      <small v-if="attachments.length">{{ attachments.length }} image attached</small>
      <button type="submit" :disabled="disabled || (!text.trim() && !attachments.length)">Send</button>
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import ImageUpload from './ImageUpload.vue'

defineProps({
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['send', 'upload-image'])
const text = ref('')
const attachments = ref([])

function handleUpload(file) {
  emit('upload-image', {
    file,
    onSuccess: (attachment) => attachments.value.push(attachment)
  })
}

function submit() {
  const value = text.value.trim()
  if (!value && !attachments.value.length) return
  emit('send', { message: value || 'Analyze the uploaded image.', attachments: attachments.value })
  text.value = ''
  attachments.value = []
}
</script>
