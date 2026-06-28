<template>
  <label class="image-upload">
    <span>Image</span>
    <input type="file" accept="image/*" :disabled="disabled" @change="handleChange" />
  </label>
</template>

<script setup>
defineProps({
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['upload'])

function handleChange(event) {
  const file = event.target.files?.[0]
  if (file) emit('upload', file)
  event.target.value = ''
}
</script>

