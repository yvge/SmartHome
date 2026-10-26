<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  ArrowUp,
  Brain,
  ChevronRight,
  Database,
  Droplets,
  History,
  Home,
  Loader2,
  MessageSquare,
  Mic,
  Plus,
  Square,
  Thermometer,
  Trash2,
  Waves,
  Wrench,
  X,
  Zap,
} from 'lucide-vue-next'
import ChatMessage from '@/components/ChatMessage.vue'
import { useChatStore } from '@/stores/chat'
import { useHomeStore } from '@/stores/home'
import { useUiStore } from '@/stores/ui'
import { formatNumber, formatTime, formatWatt, relativeTime, statusLabel } from '@/utils/format'
import type { ChatSession, ParsedIntent } from '@/types'

const route = useRoute()
const router = useRouter()
const chat = useChatStore()
const home = useHomeStore()
const ui = useUiStore()

const draft = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const nearBottom = ref(true)
const listening = ref(false)
const interimText = ref('')
const voiceUsed = ref(false)
const voiceBase = ref('')
let recognition: any = null

const prompts = [
  {
    title: '打开客厅主灯，亮度调到 80%',
    hint: '说一句，灯就亮',
  },
  {
    title: '空调调到 26 度',
    hint: '带记忆的多轮对话',
  },
  {
    title: '开启回家模式',
    hint: '一连串动作，自动完成',
  },
  {
    title: '空调多少度最省电？',
    hint: '从知识库里找答案',
  },
]

const intentTypeLabel: Record<string, string> = {
  control: '设备控制',
  query: '状态查询',
  scene: '场景执行',
  chat: '闲聊',
  knowledge: '知识问答',
  clarify: '澄清确认',
}

const latestIntent = computed<ParsedIntent | null>(() => chat.latestIntent)
const latestRetrieval = computed(() => chat.latestRetrieval)
const latestTools = computed(() => chat.lastAssistant?.tools || [])
const retrievalHits = computed(() => {
  const retrieval = latestRetrieval.value
  if (!retrieval) return []
  return [...retrieval.intents, ...retrieval.knowledge].slice(0, 4)
})

const confidence = computed(() => Math.round((latestIntent.value?.confidence || 0) * 100))
const confidenceTone = computed(() => {
  if (!latestIntent.value) return 'neutral'
  if (confidence.value >= 80) return 'good'
  if (confidence.value >= 60) return 'warn'
  return 'bad'
})

const ragSummary = computed(() => {
  const rag = home.status?.rag
  if (!rag) return 'RAG 初始化中'
  return `${rag.backend === 'milvus' ? 'Milvus' : '本地向量库'} · ${rag.count} 条知识`
})

const assistantMode = computed(() => {
  if (!home.status) return '连接中'
  return home.status.llm.enabled ? home.status.llm.model : '离线规则引擎'
})

const showScrollButton = computed(() => !nearBottom.value)

const sessionTitle = computed(
  () => chat.sessions.find((session) => session.id === chat.sessionId)?.title || '新的对话',
)

function isLatestAssistant(index: number): boolean {
  if (index !== chat.messages.length - 1) return false
  return chat.messages[index]?.role === 'assistant'
}

function scrollToBottom(smooth = true) {
  nextTick(() => {
    const element = messagesEl.value
    if (!element) return
    element.scrollTo({
      top: element.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    })
    nearBottom.value = true
  })
}

function handleScroll() {
  const element = messagesEl.value
  if (!element) return
  nearBottom.value = element.scrollHeight - element.scrollTop - element.clientHeight < 90
}

function resizeTextarea() {
  const element = textareaEl.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${Math.min(148, element.scrollHeight)}px`
}

watch(draft, () => nextTick(resizeTextarea))

async function sendText(text?: string) {
  const value = (text ?? draft.value).trim()
  if (!value || chat.streaming) return
  draft.value = ''
  await nextTick(resizeTextarea)
  scrollToBottom()
  const voice = voiceUsed.value
  voiceUsed.value = false
  await chat.send(value, { voice })
  scrollToBottom()
}

function usePrompt(prompt: string) {
  if (chat.streaming) return
  sendText(prompt)
}

function onComposerKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    sendText()
  }
}

function handleOption(label: string) {
  if (chat.streaming) return
  sendText(label)
}

function newChat() {
  chat.newSession()
  draft.value = ''
  nextTick(() => {
    textareaEl.value?.focus()
    scrollToBottom(false)
  })
}

async function openHistory() {
  chat.historyOpen = true
  await chat.loadSessions()
}

function closeHistory() {
  chat.historyOpen = false
}

async function selectSession(session: ChatSession) {
  await chat.openSession(session.id)
  closeHistory()
  scrollToBottom(false)
}

function removeSession(session: ChatSession, event: Event) {
  event.stopPropagation()
  chat.deleteSession(session.id)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && chat.historyOpen) closeHistory()
}

function toggleMic() {
  if (listening.value) {
    recognition?.stop()
    return
  }
  const SpeechRecognition =
    (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  if (!SpeechRecognition) {
    ui.warning('当前浏览器不支持语音识别，建议使用 Chrome 或 Edge')
    return
  }
  try {
    recognition = new SpeechRecognition()
    recognition.lang = 'zh-CN'
    recognition.interimResults = true
    recognition.continuous = false
    recognition.maxAlternatives = 1
    voiceBase.value = draft.value
    recognition.onstart = () => {
      listening.value = true
      interimText.value = ''
    }
    recognition.onresult = (event: any) => {
      let finalText = ''
      let interim = ''
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (result.isFinal) finalText += result[0].transcript
        else interim += result[0].transcript
      }
      interimText.value = interim
      if (finalText) {
        draft.value = `${voiceBase.value}${finalText}`.trim()
        voiceUsed.value = true
      }
    }
    recognition.onerror = (event: any) => {
      listening.value = false
      interimText.value = ''
      if (event.error === 'not-allowed') ui.warning('麦克风权限未开启')
      else if (event.error !== 'aborted') ui.warning('语音识别未成功，请重试')
    }
    recognition.onend = () => {
      listening.value = false
      interimText.value = ''
      nextTick(() => {
        resizeTextarea()
        textareaEl.value?.focus()
      })
    }
    recognition.start()
  } catch {
    ui.warning('语音识别启动失败')
    listening.value = false
  }
}

watch(
  () => chat.messages.length,
  () => {
    if (nearBottom.value) scrollToBottom()
  },
)

watch(
  () => chat.lastAssistant?.content?.length || 0,
  () => {
    if (nearBottom.value) scrollToBottom(false)
  },
)

watch(
  () => route.query.prompt,
  (prompt) => {
    if (typeof prompt === 'string' && prompt) {
      draft.value = prompt
      router.replace({ path: '/chat' })
      nextTick(() => textareaEl.value?.focus())
    }
  },
)

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  await chat.initialize()
  if (!chat.messages.length) {
    const prompt = route.query.prompt
    if (typeof prompt === 'string' && prompt) {
      draft.value = prompt
      router.replace({ path: '/chat' })
    }
  }
  scrollToBottom(false)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  recognition?.stop()
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
})
</script>

<template>
  <div class="chat-page">
    <section class="chat-shell panel">
      <header class="chat-head">
        <div class="chat-identity">
          <div class="identity-orb">
            <Home :size="17" />
          </div>
          <div class="identity-copy">
            <div class="identity-name">
              小居
              <span class="identity-badge">家庭管家</span>
            </div>
            <div class="identity-meta">
              <span class="live-dot"></span>
              {{ assistantMode }}
              <span class="dot-sep"></span>
              {{ ragSummary }}
            </div>
          </div>
        </div>
        <div class="chat-head-actions">
          <span class="session-chip" :title="sessionTitle">{{ sessionTitle }}</span>
          <button class="icon-btn sm" title="历史对话" @click="openHistory">
            <History :size="14" />
          </button>
          <button class="btn btn-sm" @click="newChat">
            <Plus :size="13" />
            新对话
          </button>
        </div>
      </header>

      <div ref="messagesEl" class="chat-scroll" @scroll.passive="handleScroll">
        <div v-if="chat.loading && !chat.messages.length" class="chat-loading">
          <Loader2 :size="18" class="spin" />
          <span>正在载入对话记录…</span>
        </div>

        <div v-else-if="!chat.messages.length" class="welcome">
          <div class="welcome-kicker">小居 · 家庭 AI 管家</div>
          <h1>今天想让家里<br />变成什么样？</h1>
          <p class="welcome-sub">说一句话，我来理解、检索，再把设备与场景安排妥当。</p>

          <div class="welcome-prompts">
            <button
              v-for="(prompt, index) in prompts"
              :key="prompt.title"
              class="welcome-prompt"
              @click="usePrompt(prompt.title)"
            >
              <span class="prompt-index mono">{{ String(index + 1).padStart(2, '0') }}</span>
              <div class="prompt-copy">
                <span class="prompt-title">{{ prompt.title }}</span>
                <span class="prompt-hint">{{ prompt.hint }}</span>
              </div>
              <ChevronRight :size="13" class="prompt-arrow" />
            </button>
          </div>

          <p class="welcome-note">支持 设备控制 · 场景编排 · 知识问答 · 状态查询</p>
        </div>

        <div v-else class="message-list">
          <ChatMessage
            v-for="(message, index) in chat.messages"
            :key="message.id"
            :message="message"
            :is-latest="isLatestAssistant(index)"
            @select-option="handleOption"
          />
        </div>
      </div>

      <Transition name="fade">
        <button v-if="showScrollButton" class="scroll-bottom" @click="scrollToBottom()">
          <ArrowDown :size="14" />
        </button>
      </Transition>

      <footer class="composer">
        <div v-if="listening" class="voice-live">
          <span class="voice-wave"><i></i><i></i><i></i><i></i></span>
          正在聆听{{ interimText ? `：${interimText}` : '…' }}
        </div>
        <div class="composer-box" :class="{ listening }">
          <textarea
            ref="textareaEl"
            v-model="draft"
            class="composer-input"
            rows="1"
            maxlength="1000"
            placeholder="告诉小居你想做什么，例如：打开客厅主灯，亮度调到 80%"
            :disabled="false"
            @keydown="onComposerKeydown"
          ></textarea>
          <div class="composer-actions">
            <button
              class="mic-btn"
              :class="{ active: listening }"
              :title="listening ? '停止语音输入' : '语音输入'"
              @click="toggleMic"
            >
              <Mic :size="16" />
            </button>
            <button
              v-if="!chat.streaming"
              class="send-btn"
              :disabled="!draft.trim()"
              title="发送"
              @click="sendText()"
            >
              <ArrowUp :size="16" />
            </button>
            <button v-else class="send-btn stop" title="停止生成" @click="chat.stop()">
              <Square :size="13" />
            </button>
          </div>
        </div>
        <div class="composer-foot">
          <span>Enter 发送 · Shift + Enter 换行 · 支持中文语音输入</span>
          <span v-if="draft.length > 800" class="char-count">{{ draft.length }} / 1000</span>
          <span v-else class="composer-mode">{{ chat.mode === 'llm' ? 'LLM 推理' : '离线规则' }}</span>
        </div>
      </footer>
    </section>

    <aside class="chat-aside">
      <section class="panel side-panel">
        <div class="side-head">
          <div>
            <div class="panel-title small">本轮上下文</div>
          </div>
          <span class="chip" :class="chat.streaming ? 'mint' : 'neutral'">
            <span v-if="chat.streaming" class="chip-dot"></span>
            {{ chat.streaming ? '推理中' : '待命' }}
          </span>
        </div>

        <div class="context-grid">
          <div class="context-item">
            <span>推理模式</span>
            <strong>{{ home.status?.llm.enabled ? 'LLM + Rules' : 'Rules Only' }}</strong>
          </div>
          <div class="context-item">
            <span>向量库</span>
            <strong>{{ home.status?.rag.backend === 'milvus' ? 'Milvus' : 'Local' }}</strong>
          </div>
          <div class="context-item">
            <span>工具数</span>
            <strong>10</strong>
          </div>
          <div class="context-item">
            <span>记忆轮次</span>
            <strong>{{ Math.floor(chat.messages.length / 2) }}</strong>
          </div>
        </div>

        <div class="side-divider"></div>

        <div v-if="latestIntent" class="intent-block">
          <div class="intent-top">
            <span class="intent-type">{{ intentTypeLabel[latestIntent.intent_type] || latestIntent.intent_type }}</span>
            <span class="intent-confidence" :class="confidenceTone">{{ confidence }}%</span>
          </div>
          <div class="intent-name mono">{{ latestIntent.intent }}</div>
          <div class="confidence-bar"><span :class="confidenceTone" :style="{ width: `${confidence}%` }"></span></div>
          <div v-if="latestIntent.actions.length" class="intent-actions">
            <span v-for="(action, index) in latestIntent.actions" :key="index" class="intent-action">
              {{ action.label || action.intent }}
            </span>
          </div>
          <div v-else-if="latestIntent.clarify" class="intent-clarify">{{ latestIntent.clarify }}</div>
        </div>
        <div v-else class="side-empty">
          <Brain :size="18" />
          <span>发送一条指令后，这里会展示意图、置信度与解析出的设备动作。</span>
        </div>
      </section>

      <section class="panel side-panel">
        <div class="side-head">
          <div>
            <div class="panel-title small">知识召回</div>
          </div>
          <span v-if="latestRetrieval" class="side-latency mono">{{ latestRetrieval.latency_ms.toFixed(1) }}ms</span>
        </div>

        <div v-if="retrievalHits.length" class="retrieval-list">
          <div v-for="hit in retrievalHits" :key="hit.id" class="retrieval-hit">
            <div class="retrieval-top">
              <span class="retrieval-kind" :class="hit.kind">{{ hit.kind === 'intent' ? '意图' : '知识' }}</span>
              <span class="retrieval-text">{{ hit.text }}</span>
              <span class="retrieval-score mono">{{ Math.round(hit.score * 100) }}%</span>
            </div>
            <div class="retrieval-bar"><span :style="{ width: `${Math.max(5, hit.score * 100)}%` }"></span></div>
          </div>
        </div>
        <div v-else class="side-empty">
          <Database :size="18" />
          <span>检索结果会在这里实时出现。当前知识库已索引 {{ home.status?.rag.count || '—' }} 条语料。</span>
        </div>

        <div v-if="latestRetrieval" class="retrieval-foot">
          <span>{{ latestRetrieval.backend }}</span>
          <span>{{ latestRetrieval.intents.length }} 意图 / {{ latestRetrieval.knowledge.length }} 知识</span>
        </div>
      </section>

      <section v-if="latestTools.length" class="panel side-panel">
        <div class="side-head">
          <div>
            <div class="panel-title small">工具调用</div>
          </div>
          <Wrench :size="13" class="dim" />
        </div>
        <div class="tool-mini-list">
          <div v-for="tool in latestTools.slice(-4)" :key="tool.callId" class="tool-mini" :class="tool.status">
            <span class="tool-mini-dot"></span>
            <div class="tool-mini-copy">
              <span class="tool-mini-name">{{ tool.label }}</span>
              <span class="tool-mini-msg">{{ tool.message || tool.name }}</span>
            </div>
            <span class="tool-mini-state">{{ statusLabel(tool.status === 'ok' ? 'success' : tool.status === 'error' ? 'failed' : 'running') }}</span>
          </div>
        </div>
      </section>

      <section class="panel side-panel environment-side">
        <div class="side-head">
          <div>
            <div class="panel-title small">环境快照</div>
          </div>
          <span class="live-dot"></span>
        </div>
        <div class="env-grid">
          <div><Thermometer :size="12" /><span>温度</span><strong>{{ home.environment.indoor_temp }}°</strong></div>
          <div><Droplets :size="12" /><span>湿度</span><strong>{{ home.environment.humidity }}%</strong></div>
          <div><Waves :size="12" /><span>PM2.5</span><strong>{{ home.environment.pm25 }}</strong></div>
          <div><Zap :size="12" /><span>功率</span><strong>{{ formatWatt(home.environment.power_w) }}</strong></div>
        </div>
      </section>
    </aside>

    <Teleport to="body">
      <Transition name="fade">
        <div v-if="chat.historyOpen" class="history-backdrop" @click.self="closeHistory">
          <div class="history-panel" role="dialog" aria-modal="true" aria-label="历史对话">
            <header class="history-head">
              <div>
                <h3>历史对话</h3>
              </div>
              <button class="icon-btn sm" aria-label="关闭" @click="closeHistory">
                <X :size="14" />
              </button>
            </header>
            <div class="history-list">
              <button
                v-for="session in chat.sessions"
                :key="session.id"
                class="history-row"
                :class="{ active: session.id === chat.sessionId }"
                @click="selectSession(session)"
              >
                <div class="history-icon"><MessageSquare :size="14" /></div>
                <div class="history-copy">
                  <span class="history-title">{{ session.title }}</span>
                  <span class="history-meta">{{ relativeTime(session.updated_at) }} · {{ session.message_count }} 条消息</span>
                </div>
                <button class="history-delete" title="删除对话" @click="removeSession(session, $event)">
                  <Trash2 :size="12" />
                </button>
              </button>
              <div v-if="!chat.sessions.length" class="empty-state">
                <MessageSquare :size="20" />
                <span>还没有历史对话</span>
              </div>
            </div>
            <footer class="history-foot">
              <button class="btn btn-sm btn-primary" @click="newChat(); closeHistory()">
                <Plus :size="12" /> 开始新对话
              </button>
            </footer>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.chat-page {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 306px;
  gap: 18px;
  height: calc(100dvh - var(--topbar-h));
  min-height: 0;
  max-width: 1560px;
  margin: 0 auto;
  padding: 20px 30px 20px;
}

.chat-shell {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 22px;
  border-bottom: 1px solid var(--line);
  flex: 0 0 auto;
}

.chat-identity {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
}

.identity-orb {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: #fbf7f0;
  background: var(--ink);
}

.identity-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
}

.identity-badge {
  font-size: 9.5px;
  font-weight: 400;
  letter-spacing: 0.02em;
  color: var(--text-3);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--line);
}

.identity-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  max-width: 100%;
  font-size: 10.5px;
  color: var(--text-3);
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.live-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--mint);
}

.dot-sep {
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: var(--text-4);
  margin: 0 2px;
}

.chat-head-actions {
  display: flex;
  align-items: center;
  gap: 7px;
  flex: 0 0 auto;
}

.session-chip {
  max-width: 150px;
  font-size: 10.5px;
  color: var(--text-4);
  padding: 3px 7px;
  border-radius: 5px;
  border: 1px solid var(--line);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 22px 22px 10px;
  scroll-behavior: smooth;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 860px;
  margin: 0 auto;
}

.chat-loading {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-3);
  font-size: 11px;
}

/* welcome */
.welcome {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 10px 0 24px;
}

.welcome-kicker {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 13px;
  letter-spacing: 0.03em;
  color: var(--mint);
  margin-bottom: 18px;
}

.welcome-kicker::before {
  content: '';
  display: block;
  width: 36px;
  height: 1px;
  margin: 0 auto 14px;
  background: var(--mint);
  opacity: 0.45;
}

.welcome h1 {
  font-size: clamp(34px, 3.4vw, 48px);
  font-weight: 500;
  line-height: 1.12;
  letter-spacing: -0.055em;
}

.welcome-sub {
  max-width: 460px;
  color: var(--text-3);
  font-size: 13px;
  line-height: 1.8;
  margin-top: 14px;
}

.welcome-prompts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  width: min(700px, 100%);
  margin-top: 30px;
  border-top: 1px solid var(--line);
}

.welcome-prompt {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 14px 4px;
  border: none;
  border-bottom: 1px solid var(--line);
  border-radius: 0;
  background: transparent;
  text-align: left;
  transition: background 0.18s ease;
}

.welcome-prompt:nth-child(odd) {
  padding-right: 18px;
  border-right: 1px solid var(--line);
}

.welcome-prompt:nth-child(even) {
  padding-left: 18px;
}

.welcome-prompt:hover {
  background: rgba(41, 37, 36, 0.025);
}

.prompt-index {
  font-family: var(--font-serif);
  font-size: 12px;
  color: var(--text-4);
  width: 20px;
  flex: 0 0 20px;
  transition: color 0.18s ease;
}

.welcome-prompt:hover .prompt-index {
  color: var(--mint);
}

.prompt-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.prompt-title {
  font-size: 13px;
  color: var(--text);
  line-height: 1.45;
}

.prompt-hint {
  font-size: 10.5px;
  color: var(--text-4);
}

.prompt-arrow {
  color: var(--text-4);
  flex: 0 0 auto;
  opacity: 0.6;
  transition: transform 0.18s ease, opacity 0.18s ease, color 0.18s ease;
}

.welcome-prompt:hover .prompt-arrow {
  opacity: 1;
  transform: translateX(2px);
  color: var(--mint);
}

.welcome-note {
  margin-top: 22px;
  font-size: 10.5px;
  color: var(--text-4);
  letter-spacing: 0.06em;
}

/* composer */
.composer {
  flex: 0 0 auto;
  padding: 12px 22px 16px;
  border-top: 1px solid var(--line);
  background: transparent;
}

.voice-live {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: var(--mint);
  padding: 0 4px 7px;
}

.voice-wave {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 12px;
}

.voice-wave i {
  width: 2px;
  height: 5px;
  border-radius: 99px;
  background: var(--mint);
  animation: voice-bars 0.8s ease infinite;
}

.voice-wave i:nth-child(2) {
  animation-delay: 0.12s;
}

.voice-wave i:nth-child(3) {
  animation-delay: 0.24s;
}

.voice-wave i:nth-child(4) {
  animation-delay: 0.36s;
}

@keyframes voice-bars {
  0%,
  100% {
    height: 4px;
    opacity: 0.5;
  }
  50% {
    height: 12px;
    opacity: 1;
  }
}

.composer-box {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 9px 9px 9px 14px;
  border-radius: 12px;
  border: 1px solid var(--line-strong);
  background: var(--panel);
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.composer-box:focus-within {
  border-color: var(--mint);
  box-shadow: 0 0 0 3px rgba(180, 74, 38, 0.08);
}

.composer-box.listening {
  border-color: var(--mint);
  box-shadow: 0 0 0 3px rgba(180, 74, 38, 0.08);
}

.composer-input {
  flex: 1;
  min-height: 24px;
  max-height: 148px;
  border: none;
  background: transparent;
  outline: none;
  resize: none;
  color: var(--text);
  font-size: 13.5px;
  line-height: 1.65;
  padding: 4px 0;
}

.composer-input::placeholder {
  color: var(--text-4);
}

.composer-actions {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 0 0 auto;
}

.mic-btn,
.send-btn {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid transparent;
  display: grid;
  place-items: center;
  transition: all 0.17s ease;
}

.mic-btn {
  color: var(--text-3);
  background: transparent;
  border-color: var(--line);
}

.mic-btn:hover {
  color: var(--mint);
  background: var(--mint-soft);
  border-color: var(--mint-line);
}

.mic-btn.active {
  color: #fffaf5;
  background: var(--mint);
  border-color: transparent;
  animation: pulse-soft 1.4s ease infinite;
}

.send-btn {
  color: #fffaf5;
  background: var(--mint);
}

.send-btn:hover {
  background: #9c3d1e;
}

.send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  box-shadow: none;
}

.send-btn.stop {
  background: var(--critical-soft);
  color: var(--critical);
  border-color: rgba(168, 58, 50, 0.2);
}

.composer-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 7px 2px 0;
  font-size: 10px;
  color: var(--text-4);
}

.composer-mode {
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--text-4);
}

.char-count {
  color: var(--warning);
  font-variant-numeric: tabular-nums;
}

.scroll-bottom {
  position: absolute;
  right: 26px;
  bottom: 108px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  border: 1px solid var(--line-strong);
  background: var(--panel-solid);
  color: var(--text-2);
  box-shadow: 0 8px 20px rgba(60, 45, 30, 0.1);
  z-index: 3;
}

.chat-shell {
  position: relative;
}

/* aside */
.chat-aside {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 2px;
}

.side-panel {
  padding: 16px;
}

.side-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.side-latency {
  font-size: 8.5px;
  color: var(--text-4);
}

.context-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0;
  border-top: 1px solid var(--line);
}

.context-item {
  padding: 9px 2px;
  border: none;
  border-bottom: 1px solid var(--line);
  border-radius: 0;
  background: transparent;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.context-item:nth-child(odd) {
  padding-right: 10px;
  border-right: 1px solid var(--line);
}

.context-item:nth-child(even) {
  padding-left: 12px;
}

.context-item:nth-child(n + 3) {
  border-bottom: none;
}

.context-item span {
  font-size: 9.5px;
  color: var(--text-4);
}

.context-item strong {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text-2);
}

.side-divider {
  height: 1px;
  background: var(--line);
  margin: 11px 0;
}

.intent-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.intent-type {
  font-size: 11px;
  color: var(--text);
  font-weight: 500;
}

.intent-confidence {
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  color: var(--text-3);
}

.intent-confidence.good {
  color: var(--mint);
}

.intent-confidence.warn {
  color: var(--warning);
}

.intent-confidence.bad {
  color: var(--critical);
}

.intent-name {
  font-size: 9.5px;
  color: var(--text-4);
  margin-top: 2px;
}

.confidence-bar {
  height: 2px;
  border-radius: 99px;
  background: rgba(41, 37, 36, 0.06);
  margin-top: 7px;
  overflow: hidden;
}

.confidence-bar span {
  display: block;
  height: 100%;
  background: var(--mint);
  border-radius: inherit;
}

.confidence-bar span.warn {
  background: var(--warning);
}

.confidence-bar span.bad {
  background: var(--critical);
}

.intent-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.intent-action {
  font-size: 9.5px;
  color: var(--text-2);
  padding: 3px 7px;
  border-radius: 4px;
  background: rgba(180, 74, 38, 0.05);
  border: 1px solid rgba(180, 74, 38, 0.1);
  line-height: 1.5;
}

.intent-clarify {
  font-size: 9.5px;
  color: var(--warning);
  margin-top: 7px;
  line-height: 1.5;
}

.side-empty {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 10.5px;
  line-height: 1.6;
  color: var(--text-4);
  padding: 8px 0;
}

.side-empty svg {
  flex: 0 0 auto;
  margin-top: 1px;
}

.retrieval-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.retrieval-hit {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.retrieval-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.retrieval-kind {
  flex: 0 0 auto;
  font-size: 7.5px;
  color: var(--indigo);
  background: var(--indigo-soft);
  padding: 1px 4px;
  border-radius: 3px;
}

.retrieval-kind.knowledge {
  color: var(--amber);
  background: var(--amber-soft);
}

.retrieval-text {
  flex: 1;
  font-size: 9.5px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.retrieval-score {
  font-size: 8px;
  color: var(--text-4);
}

.retrieval-bar {
  height: 2px;
  border-radius: 99px;
  background: rgba(41, 37, 36, 0.05);
  overflow: hidden;
}

.retrieval-bar span {
  display: block;
  height: 100%;
  background: color-mix(in srgb, var(--mint) 65%, transparent);
}

.retrieval-foot {
  display: flex;
  justify-content: space-between;
  margin-top: 9px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
  font-size: 8px;
  color: var(--text-4);
  font-family: var(--font-mono);
}

.tool-mini-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.tool-mini {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.tool-mini-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  margin-top: 4px;
  background: var(--text-4);
  flex: 0 0 4px;
}

.tool-mini.ok .tool-mini-dot {
  background: var(--good);
}

.tool-mini.error .tool-mini-dot {
  background: var(--critical);
}

.tool-mini.running .tool-mini-dot {
  background: var(--mint);
  animation: pulse-soft 1.2s infinite;
}

.tool-mini-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.tool-mini-name {
  font-size: 9.5px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-mini-msg {
  font-size: 8px;
  color: var(--text-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-mini-state {
  font-size: 8px;
  color: var(--text-4);
}

.env-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.env-grid > div {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0 5px;
  padding: 7px 8px;
  border-radius: 8px;
  border: 1px solid rgba(41, 37, 36, 0.06);
  background: rgba(41, 37, 36, 0.015);
  color: var(--text-3);
}

.env-grid svg {
  grid-row: span 2;
  align-self: center;
  color: var(--text-4);
}

.env-grid span {
  font-size: 8px;
  color: var(--text-4);
}

.env-grid strong {
  font-size: 10px;
  color: var(--text-2);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.spin {
  animation: spin 0.9s linear infinite;
}

/* history modal */
.history-backdrop {
  position: fixed;
  inset: 0;
  z-index: 360;
  display: flex;
  justify-content: flex-end;
  background: rgba(33, 29, 25, 0.3);
  backdrop-filter: blur(6px);
}

.history-panel {
  width: min(400px, 100vw);
  height: 100%;
  background: #f7f2ea;
  border-left: 1px solid var(--line-strong);
  box-shadow: -30px 0 80px rgba(60, 45, 30, 0.12);
  display: flex;
  flex-direction: column;
  padding: 20px;
}

.history-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.history-head h3 {
  font-size: 18px;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-row {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  width: 100%;
  transition: background 0.16s ease, border-color 0.16s ease;
}

.history-row:hover {
  background: rgba(41, 37, 36, 0.03);
}

.history-row.active {
  background: var(--mint-soft);
  border-color: rgba(180, 74, 38, 0.15);
}

.history-icon {
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: var(--text-3);
  background: rgba(41, 37, 36, 0.035);
}

.history-row.active .history-icon {
  color: var(--mint);
  background: rgba(180, 74, 38, 0.08);
}

.history-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.history-title {
  font-size: 11.5px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-meta {
  font-size: 8.5px;
  color: var(--text-4);
}

.history-delete {
  border: none;
  background: transparent;
  color: var(--text-4);
  padding: 4px;
  border-radius: 5px;
  opacity: 0;
  transition: opacity 0.15s ease, color 0.15s ease;
}

.history-row:hover .history-delete {
  opacity: 1;
}

.history-delete:hover {
  color: var(--critical);
  background: var(--critical-soft);
}

.history-foot {
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

@media (max-width: 1320px) {
  .chat-page {
    grid-template-columns: minmax(0, 1fr) 280px;
    padding: 16px 18px;
  }
}

@media (max-width: 1120px) {
  .chat-page {
    grid-template-columns: minmax(0, 1fr);
    padding: 14px 18px;
  }

  .chat-aside {
    display: none;
  }
}

@media (max-width: 760px) {
  .chat-page {
    height: calc(100dvh - var(--topbar-h) - 66px);
    padding: 10px 10px 8px;
  }

  .chat-head {
    padding: 10px 12px;
  }

  .identity-badge,
  .session-chip,
  .identity-meta {
    display: none;
  }

  .chat-identity {
    min-width: 0;
  }

  .chat-scroll {
    padding: 16px 12px 8px;
  }

  .welcome-prompts {
    grid-template-columns: 1fr;
  }

  .welcome h1 {
    font-size: 27px;
  }

  .welcome-caps {
    display: none;
  }

  .composer {
    padding: 7px 10px 10px;
  }

  .composer-foot {
    display: none;
  }

  .chat-head-actions .btn {
    padding: 0 9px;
  }
}
</style>
