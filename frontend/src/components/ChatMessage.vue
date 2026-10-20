<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  Copy,
  Loader2,
  Sparkles,
  Square,
  Volume2,
} from 'lucide-vue-next'
import AgentTrace from '@/components/AgentTrace.vue'
import type { ChatUiMessage } from '@/types'
import { formatTime, statusLabel } from '@/utils/format'
import { useUiStore } from '@/stores/ui'

const props = withDefaults(
  defineProps<{
    message: ChatUiMessage
    isLatest?: boolean
  }>(),
  { isLatest: false },
)

const emit = defineEmits<{ (event: 'select-option', label: string): void }>()
const router = useRouter()
const ui = useUiStore()
const copied = ref(false)
const speaking = ref(false)
let speakTimer: number | undefined

const isAssistant = computed(() => props.message.role === 'assistant')
const runningNode = computed(() =>
  [...props.message.trace].reverse().find((node) => node.status === 'running'),
)
const statusTone = computed(() => {
  const status = props.message.status
  if (status === 'success') return 'good'
  if (status === 'partial' || status === 'fallback' || status === 'skipped') return 'warn'
  if (status === 'failed' || status === 'stopped') return 'bad'
  return 'neutral'
})
const showStatus = computed(
  () => isAssistant.value && props.message.status && props.message.status !== 'running',
)
const modeText = computed(() => {
  if (props.message.mode === 'llm') return 'LLM'
  if (props.message.mode === 'offline') return '规则引擎'
  return ''
})

async function copy() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1600)
  } catch {
    ui.error('复制失败，请手动选择文本')
  }
}

function speak() {
  if (!('speechSynthesis' in window) || !props.message.content) {
    ui.warning('当前浏览器不支持语音朗读')
    return
  }
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(props.message.content)
  utterance.lang = 'zh-CN'
  utterance.rate = 1.02
  const chineseVoice = window.speechSynthesis
    .getVoices()
    .find((voice) => voice.lang.toLowerCase().startsWith('zh'))
  if (chineseVoice) utterance.voice = chineseVoice
  utterance.onend = () => {
    speaking.value = false
    window.clearTimeout(speakTimer)
  }
  utterance.onerror = () => {
    speaking.value = false
    window.clearTimeout(speakTimer)
  }
  speaking.value = true
  window.speechSynthesis.speak(utterance)
  speakTimer = window.setTimeout(() => {
    speaking.value = false
  }, Math.max(4000, props.message.content.length * 220))
}

function stopSpeaking() {
  window.speechSynthesis?.cancel()
  speaking.value = false
}

function openExecution() {
  if (props.message.executionId) {
    router.push({ path: '/executions', query: { focus: props.message.executionId } })
  } else {
    router.push('/executions')
  }
}

onBeforeUnmount(() => {
  if (speaking.value) window.speechSynthesis?.cancel()
  window.clearTimeout(speakTimer)
})
</script>

<template>
  <div v-if="!isAssistant" class="user-row">
    <div class="user-bubble">
      <div class="user-text">{{ message.content }}</div>
      <div class="user-time">{{ formatTime(message.createdAt) }}</div>
    </div>
  </div>

  <div v-else class="assistant-row">
    <div class="assistant-avatar">
      <Sparkles :size="15" />
    </div>
    <div class="assistant-main">
      <div class="assistant-head">
        <span class="assistant-name">小居</span>
        <span v-if="modeText" class="mode-badge" :class="{ llm: message.mode === 'llm' }">{{ modeText }}</span>
        <span v-if="showStatus" class="msg-status" :class="statusTone">
          {{ statusLabel(message.status) }}
        </span>
        <span class="assistant-time">{{ formatTime(message.createdAt) }}</span>
        <span v-if="message.streaming && runningNode" class="thinking-inline">
          <Loader2 :size="10" class="spin" />
          {{ runningNode.label }}中
        </span>
      </div>

      <div class="assistant-bubble" :class="{ streaming: message.streaming, failed: message.status === 'failed' }">
        <div v-if="message.streaming && !message.content" class="typing">
          <span></span><span></span><span></span>
        </div>
        <div v-else class="answer-text">
          {{ message.content }}<span v-if="message.streaming" class="caret"></span>
        </div>

        <div v-if="message.error && message.status === 'failed'" class="error-line">
          <AlertCircle :size="12" />
          <span>{{ message.error }}</span>
        </div>

        <div v-if="message.options?.length" class="clarify-options">
          <span class="clarify-label">{{ message.options.length > 1 ? '请选择目标：' : '继续：' }}</span>
          <button
            v-for="option in message.options"
            :key="option.device_id || option.label"
            class="clarify-chip"
            :disabled="message.streaming"
            @click="emit('select-option', option.label)"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <AgentTrace
        v-if="message.trace.length || message.intent || message.retrieval || message.tools.length || message.scene"
        :trace="message.trace"
        :intent="message.intent"
        :retrieval="message.retrieval"
        :tools="message.tools"
        :notes="message.notes"
        :scene="message.scene"
        :streaming="message.streaming"
        :default-open="isLatest"
      />

      <div v-if="(message.content || message.executionId) && !message.streaming" class="message-actions">
        <button class="msg-action" title="复制回复" @click="copy">
          <Check v-if="copied" :size="11" />
          <Copy v-else :size="11" />
          {{ copied ? '已复制' : '复制' }}
        </button>
        <button v-if="message.content" class="msg-action" :class="{ active: speaking }" title="朗读回复" @click="speaking ? stopSpeaking() : speak()">
          <Volume2 :size="11" />
          {{ speaking ? '停止' : '朗读' }}
        </button>
        <button v-if="message.executionId" class="msg-action" title="查看运行轨迹" @click="openExecution">
          <ArrowUpRight :size="11" />
          运行轨迹
        </button>
        <span class="message-foot-time">{{ formatTime(message.createdAt) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.user-row {
  display: flex;
  justify-content: flex-end;
  padding-left: 15%;
}

.user-bubble {
  max-width: 620px;
  border-radius: 16px 16px 5px 16px;
  padding: 10px 14px;
  background: linear-gradient(135deg, rgba(94, 234, 212, 0.12), rgba(139, 149, 248, 0.1));
  border: 1px solid rgba(94, 234, 212, 0.12);
}

.user-text {
  font-size: 13px;
  line-height: 1.65;
  color: #eafffb;
  white-space: pre-wrap;
  word-break: break-word;
}

.user-time {
  font-size: 8.5px;
  color: rgba(154, 171, 192, 0.55);
  text-align: right;
  margin-top: 3px;
  font-variant-numeric: tabular-nums;
}

.assistant-row {
  display: flex;
  gap: 11px;
  align-items: flex-start;
  padding-right: 7%;
}

.assistant-avatar {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: #06201c;
  background: linear-gradient(140deg, var(--mint-bright), #9ba5fa);
  box-shadow: 0 0 20px rgba(94, 234, 212, 0.14);
  margin-top: 2px;
}

.assistant-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.assistant-head {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}

.assistant-name {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text);
}

.mode-badge {
  font-size: 8px;
  font-family: var(--font-mono);
  color: var(--text-4);
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid var(--line);
}

.mode-badge.llm {
  color: var(--indigo);
  background: var(--indigo-soft);
  border-color: rgba(139, 149, 248, 0.16);
}

.msg-status {
  font-size: 8.5px;
  padding: 1px 5px;
  border-radius: 4px;
  color: var(--text-3);
  background: rgba(255, 255, 255, 0.03);
}

.msg-status.good {
  color: var(--good);
  background: var(--good-soft);
}

.msg-status.warn {
  color: var(--warning);
  background: var(--amber-soft);
}

.msg-status.bad {
  color: var(--critical);
  background: var(--critical-soft);
}

.assistant-time {
  font-size: 8.5px;
  color: var(--text-4);
  font-variant-numeric: tabular-nums;
}

.thinking-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 9px;
  color: var(--mint);
}

.assistant-bubble {
  border-radius: 5px 16px 16px 16px;
  padding: 11px 14px;
  background: rgba(15, 25, 37, 0.6);
  border: 1px solid rgba(148, 178, 209, 0.09);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.12);
}

.assistant-bubble.streaming {
  border-color: rgba(94, 234, 212, 0.13);
}

.assistant-bubble.failed {
  border-color: rgba(239, 123, 123, 0.16);
}

.answer-text {
  font-size: 13px;
  line-height: 1.72;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}

.caret {
  display: inline-block;
  width: 2px;
  height: 13px;
  margin-left: 2px;
  vertical-align: -1px;
  background: var(--mint);
  animation: blink-caret 1s steps(1) infinite;
}

.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 20px;
}

.typing span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--mint);
  opacity: 0.35;
  animation: typing 1.2s ease infinite;
}

.typing span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typing {
  0%,
  60%,
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  30% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

.error-line {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(239, 123, 123, 0.12);
  color: var(--critical);
  font-size: 10px;
  line-height: 1.5;
}

.clarify-options {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 9px;
  padding-top: 9px;
  border-top: 1px solid var(--line);
}

.clarify-label {
  font-size: 9.5px;
  color: var(--text-4);
}

.clarify-chip {
  padding: 4px 9px;
  border-radius: 6px;
  border: 1px solid rgba(94, 234, 212, 0.16);
  background: var(--mint-soft);
  color: var(--mint);
  font-size: 10px;
  transition: background 0.16s ease, color 0.16s ease;
}

.clarify-chip:hover:not(:disabled) {
  background: var(--mint);
  color: #06211d;
}

.clarify-chip:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.message-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0.5;
  transition: opacity 0.18s ease;
}

.assistant-main:hover .message-actions {
  opacity: 1;
}

.msg-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  border: none;
  background: transparent;
  color: var(--text-4);
  font-size: 9px;
  border-radius: 5px;
  transition: color 0.15s ease, background 0.15s ease;
}

.msg-action:hover,
.msg-action.active {
  color: var(--text-2);
  background: rgba(255, 255, 255, 0.035);
}

.message-foot-time {
  margin-left: auto;
  font-size: 8px;
  color: var(--text-4);
  font-variant-numeric: tabular-nums;
}

.spin {
  animation: spin 0.9s linear infinite;
}

@media (max-width: 760px) {
  .user-row {
    padding-left: 8%;
  }

  .assistant-row {
    padding-right: 0;
  }

  .assistant-avatar {
    width: 27px;
    height: 27px;
    flex-basis: 27px;
    border-radius: 9px;
  }

  .answer-text {
    font-size: 12.5px;
  }
}
</style>
