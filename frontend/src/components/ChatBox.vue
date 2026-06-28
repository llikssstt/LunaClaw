<template>
  <div class="chat-box">
    <header>
      <div>
        <h1>LunaClaw Agent</h1>
        <p>Planner, tools, sources, memory, Skills, and self-evolution in one loop.</p>
      </div>
    </header>
    <MessageList :messages="messages" :loading="loading" />
    <InputBox :disabled="loading" @send="$emit('send', $event)" @upload-image="$emit('upload-image', $event)" />
  </div>
</template>

<script setup>
import InputBox from './InputBox.vue'
import MessageList from './MessageList.vue'

defineProps({
  messages: { type: Array, required: true },
  loading: { type: Boolean, default: false }
})

defineEmits(['send', 'upload-image'])
</script>
