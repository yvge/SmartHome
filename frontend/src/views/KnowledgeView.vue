<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  BookOpen,
  BrainCircuit,
  Check,
  Database,
  FileText,
  Loader2,
  Plus,
  Search,
  Server,
  Sparkles,
  X,
} from 'lucide-vue-next'
import { api } from '@/services/http'
import { useHomeStore } from '@/stores/home'
import { useUiStore } from '@/stores/ui'
import type { RAGHit } from '@/types'

interface RAGEntryRowLocal {
  id: string
  kind: 'intent' | 'knowledge'
  text: string
  intent: string
  category: string
  device_type: string
  answer: string
  metadata: Record<string, any>
}

const home = useHomeStore()
const ui = useUiStore()

const stats = ref<any>(null)
const entries = ref<RAGEntryRowLocal[]>([])
const loading = ref(true)
const kindFilter = ref<'all' | 'intent' | 'knowledge'>('all')
const query = ref('')

const searchInput = ref('空调多少度最省电')
const searchKind = ref<'all' | 'intent' | 'knowledge'>('all')
const searching = ref(false)
const searchResults = ref<RAGHit[]>([])
const searchLatency = ref(0)
const hasSearched = ref(false)

const addOpen = ref(false)
const addSaving = ref(false)
const addForm = ref({
  kind: 'knowledge' as 'knowledge' | 'intent',
  text: '',
  intent: '',
  answer: '',
  category: 'custom',
  device_type: '',
})

const ragStatus = computed(() => stats.value || home.status?.rag || null)
const filteredEntries = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return entries.value.filter((entry) => {
    if (kindFilter.value !== 'all' && entry.kind !== kindFilter.value) return false
    if (!needle) return true
    return (
      entry.text.toLowerCase().includes(needle)
      || entry.intent.toLowerCase().includes(needle)
      || entry.answer.toLowerCase().includes(needle)
    )
  })
})

const embeddingLabel = computed(() => {
  const embedding = ragStatus.value?.embedding
  if (!embedding) return '—'
  return `${embedding.model} · ${embedding.dim}d`
})

const backendLabel = computed(() => {
  const backend = ragStatus.value?.backend
  if (backend === 'milvus') return 'Milvus'
  if (backend === 'local') return '本地内存向量库'
  return '未初始化'
})

async function loadStats() {
  try {
    stats.value = await api.get('/rag/stats')
  } catch {
    // status card falls back to home store
  }
}

async function loadEntries() {
  loading.value = true
  try {
    const response = await api.get<{ entries: RAGEntryRowLocal[]; total: number }>('/rag/entries?limit=400')
    entries.value = response.entries
  } catch (error) {
    ui.toastFromError(error, '知识库加载失败')
  } finally {
    loading.value = false
  }
}

async function runSearch() {
  const text = searchInput.value.trim()
  if (!text || searching.value) return
  searching.value = true
  hasSearched.value = true
  try {
    const response = await api.post<{ hits: RAGHit[]; latency_ms: number }>('/rag/search', {
      query: text,
      top_k: 6,
      kind: searchKind.value === 'all' ? null : searchKind.value,
    })
    searchResults.value = response.hits
    searchLatency.value = response.latency_ms
  } catch (error) {
    ui.toastFromError(error, '检索失败')
  } finally {
    searching.value = false
  }
}

function useExample(text: string) {
  searchInput.value = text
  runSearch()
}

async function addEntry() {
  const form = addForm.value
  if (!form.text.trim()) {
    ui.warning('请填写示例或问题文本')
    return
  }
  if (form.kind === 'knowledge' && !form.answer.trim()) {
    ui.warning('知识类条目需要填写答案')
    return
  }
  if (form.kind === 'intent' && !form.intent.trim()) {
    ui.warning('意图示例需要填写 intent 标识')
    return
  }
  addSaving.value = true
  try {
    await api.post('/rag/entries', {
      kind: form.kind,
      text: form.text.trim(),
      intent: form.intent.trim(),
      answer: form.answer.trim(),
      category: form.category.trim() || 'custom',
      device_type: form.device_type.trim(),
      metadata: {},
    })
    ui.success('知识已写入并完成向量索引')
    addOpen.value = false
    addForm.value = { kind: 'knowledge', text: '', intent: '', answer: '', category: 'custom', device_type: '' }
    await Promise.all([loadEntries(), loadStats()])
    home.refreshStatus()
  } catch (error) {
    ui.toastFromError(error, '写入知识失败')
  } finally {
    addSaving.value = false
  }
}

function kindLabel(kind: string): string {
  return kind === 'knowledge' ? '知识' : '意图'
}

onMounted(async () => {
  await Promise.all([loadStats(), loadEntries()])
  runSearch()
})
</script>

<template>
  <div class="page knowledge-page">
    <section class="page-head">
      <div>
        <div class="eyebrow">知识与检索</div>
        <h1>意图知识库</h1>
        <p class="lede">
          你平时怎么说话，这里就怎么记。检索会找出相似的说法和家庭知识，供小居理解和回答，
          也可以随时补充新的内容。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" @click="loadEntries(); loadStats()">
          <Server :size="14" />
          刷新索引
        </button>
        <button class="btn btn-primary" @click="addOpen = true">
          <Plus :size="14" />
          添加知识
        </button>
      </div>
    </section>

    <section class="rag-stats">
      <div class="rag-stat panel">
        <div class="rag-stat-icon mint"><Database :size="16" /></div>
        <div class="rag-stat-copy">
          <span>知识条目</span>
          <strong>{{ ragStatus?.count ?? '—' }}</strong>
        </div>
        <span class="rag-stat-note">{{ ragStatus?.intents ?? '—' }} 意图 · {{ ragStatus?.knowledge ?? '—' }} 知识</span>
      </div>
      <div class="rag-stat panel">
        <div class="rag-stat-icon indigo"><BrainCircuit :size="16" /></div>
        <div class="rag-stat-copy">
          <span>向量模型</span>
          <strong class="small-value">{{ embeddingLabel }}</strong>
        </div>
        <span v-if="ragStatus?.embedding?.fallback" class="rag-stat-note warn">已降级</span>
        <span v-else class="rag-stat-note">已加载</span>
      </div>
      <div class="rag-stat panel">
        <div class="rag-stat-icon amber"><Server :size="16" /></div>
        <div class="rag-stat-copy">
          <span>向量库</span>
          <strong class="small-value">{{ backendLabel }}</strong>
        </div>
        <span class="rag-stat-note" :class="{ warn: ragStatus?.degraded }">
          {{ ragStatus?.healthy ? '健康' : '降级' }}
        </span>
      </div>
      <div class="rag-stat panel">
        <div class="rag-stat-icon blue"><Sparkles :size="16" /></div>
        <div class="rag-stat-copy">
          <span>最近检索</span>
          <strong>{{ (ragStatus?.latency_ms || searchLatency || 0).toFixed(1) }}<em>ms</em></strong>
        </div>
        <span class="rag-stat-note">COSINE 相似度</span>
      </div>
    </section>

    <div class="knowledge-main">
      <section class="panel search-panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">检索</div>
            <div class="panel-title">语义检索</div>
            <div class="panel-desc">试试不同说法，看看会召回哪些相似意图</div>
          </div>
          <span class="chip" :class="searchKind === 'knowledge' ? 'amber' : searchKind === 'intent' ? 'indigo' : 'neutral'">
            {{ searchKind === 'all' ? '全部语料' : searchKind === 'knowledge' ? '仅知识' : '仅意图' }}
          </span>
        </div>

        <div class="search-controls">
          <div class="search-input-wrap">
            <Search :size="15" />
            <input
              v-model="searchInput"
              class="search-input"
              placeholder="例如：家里有点闷，想开空调"
              aria-label="检索知识库"
              @keydown.enter="runSearch"
            />
            <button class="search-submit" :disabled="searching || !searchInput.trim()" @click="runSearch">
              <Loader2 v-if="searching" :size="13" class="spin" />
              <Search v-else :size="13" />
              检索
            </button>
          </div>
          <div class="segmented">
            <button :class="{ active: searchKind === 'all' }" @click="searchKind = 'all'; runSearch()">全部</button>
            <button :class="{ active: searchKind === 'intent' }" @click="searchKind = 'intent'; runSearch()">意图</button>
            <button :class="{ active: searchKind === 'knowledge' }" @click="searchKind = 'knowledge'; runSearch()">知识</button>
          </div>
        </div>

        <div class="example-row">
          <span class="example-label">示例</span>
          <button
            v-for="example in ['我有点冷，把温度调高', '空气净化器滤芯多久换', '开启省电模式', '把客厅灯调暖一点']"
            :key="example"
            class="example-chip"
            @click="useExample(example)"
          >
            {{ example }}
          </button>
        </div>

        <div v-if="searchResults.length" class="result-list">
          <div class="result-head">
            <span>召回 {{ searchResults.length }} 条</span>
            <span class="mono">{{ searchLatency.toFixed(1) }} ms</span>
          </div>
          <div
            v-for="(hit, index) in searchResults"
            :key="hit.id"
            class="result-card"
            :class="hit.kind"
          >
            <div class="result-rank">{{ String(index + 1).padStart(2, '0') }}</div>
            <div class="result-body">
              <div class="result-top">
                <span class="result-kind">{{ kindLabel(hit.kind) }}</span>
                <span class="result-text">{{ hit.text }}</span>
                <span class="result-score mono">{{ (hit.score * 100).toFixed(1) }}%</span>
              </div>
              <div class="result-bar">
                <span :style="{ width: `${Math.max(4, Math.min(100, hit.score * 100))}%` }"></span>
              </div>
              <div v-if="hit.answer" class="result-answer">{{ hit.answer }}</div>
              <div v-else class="result-meta">
                intent: <em>{{ hit.intent }}</em>
                <span v-if="hit.device_type"> · device: <em>{{ hit.device_type }}</em></span>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="hasSearched && !searching" class="empty-state">
          <Search :size="20" />
          <span>没有召回到相关片段，试试换个说法或添加一条知识</span>
        </div>
      </section>

      <section class="panel pipeline-panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">RAG</div>
            <div class="panel-title">检索管线</div>
          </div>
        </div>
        <ol class="pipeline">
          <li>
            <span class="pipeline-index">1</span>
            <div>
              <div class="pipeline-title">查询向量化</div>
              <div class="pipeline-desc">{{ embeddingLabel }}</div>
            </div>
          </li>
          <li>
            <span class="pipeline-index">2</span>
            <div>
              <div class="pipeline-title">相似度召回</div>
              <div class="pipeline-desc">{{ backendLabel }} · COSINE Top-K</div>
            </div>
          </li>
          <li>
            <span class="pipeline-index">3</span>
            <div>
              <div class="pipeline-title">意图示例注入</div>
              <div class="pipeline-desc">作为 few-shot 参考交给结构化解析</div>
            </div>
          </li>
          <li>
            <span class="pipeline-index">4</span>
            <div>
              <div class="pipeline-title">知识增强回答</div>
              <div class="pipeline-desc">回答只依据召回片段与真实设备状态</div>
            </div>
          </li>
        </ol>
        <div class="pipeline-foot">
          <span class="pipeline-dot"></span>
          <span v-if="ragStatus?.error">{{ ragStatus.error }}</span>
          <span v-else>向量库运行正常，检索结果实时生效</span>
        </div>
      </section>
    </div>

    <section class="panel entries-panel">
      <div class="panel-head">
        <div>
          <div class="panel-kicker">语料</div>
          <div class="panel-title">知识条目</div>
          <div class="panel-desc">展示 {{ filteredEntries.length }} / {{ entries.length }} 条语料</div>
        </div>
        <div class="entries-filters">
          <div class="segmented">
            <button :class="{ active: kindFilter === 'all' }" @click="kindFilter = 'all'">全部</button>
            <button :class="{ active: kindFilter === 'intent' }" @click="kindFilter = 'intent'">意图</button>
            <button :class="{ active: kindFilter === 'knowledge' }" @click="kindFilter = 'knowledge'">知识</button>
          </div>
          <div class="entries-search">
            <Search :size="12" />
            <input v-model="query" placeholder="筛选文本 / 意图" aria-label="筛选知识条目" />
          </div>
        </div>
      </div>

      <div v-if="loading" class="entry-loading">
        <Loader2 :size="16" class="spin" /> 正在加载知识库…
      </div>

      <div v-else class="entry-table">
        <div class="entry-row entry-header">
          <span>类型</span>
          <span>文本</span>
          <span>标识</span>
          <span>来源</span>
        </div>
        <div v-for="entry in filteredEntries.slice(0, 60)" :key="entry.id" class="entry-row">
          <span class="entry-kind" :class="entry.kind">{{ kindLabel(entry.kind) }}</span>
          <span class="entry-text">{{ entry.text }}</span>
          <span class="entry-intent mono">{{ entry.intent || '—' }}</span>
          <span class="entry-source">
            <span v-if="entry.metadata?.source === 'seed'" class="chip neutral">内置</span>
            <span v-else class="chip mint">自定义</span>
          </span>
        </div>
        <div v-if="!filteredEntries.length" class="empty-state">
          <FileText :size="18" />
          <span>没有匹配的条目</span>
        </div>
      </div>
      <div v-if="filteredEntries.length > 60" class="entry-foot">
        仅展示前 60 条，完整语料共 {{ filteredEntries.length }} 条
      </div>
    </section>

    <Teleport to="body">
      <Transition name="fade">
        <div v-if="addOpen" class="add-backdrop" @click.self="addOpen = false">
          <div class="add-panel" role="dialog" aria-modal="true" aria-label="添加知识">
            <header class="add-head">
              <div>
                <div class="panel-kicker">补充语料</div>
                <h3>添加知识 / 意图示例</h3>
              </div>
              <button class="icon-btn sm" aria-label="关闭" @click="addOpen = false"><X :size="14" /></button>
            </header>

            <div class="add-body">
              <div class="field">
                <span class="field-label">条目类型</span>
                <div class="segmented">
                  <button :class="{ active: addForm.kind === 'knowledge' }" @click="addForm.kind = 'knowledge'">知识问答</button>
                  <button :class="{ active: addForm.kind === 'intent' }" @click="addForm.kind = 'intent'">意图示例</button>
                </div>
              </div>

              <label class="field">
                <span class="field-label">
                  {{ addForm.kind === 'knowledge' ? '问题 / 说法' : '用户可能说的话' }}
                </span>
                <input v-model="addForm.text" class="input" maxlength="200" placeholder="例如：空气净化器滤芯多久换一次" />
              </label>

              <label v-if="addForm.kind === 'knowledge'" class="field">
                <span class="field-label">答案</span>
                <textarea v-model="addForm.answer" class="textarea" rows="4" maxlength="1000" placeholder="基于事实的简短回答，不要编造参数" />
              </label>

              <div v-else class="field-row">
                <label class="field">
                  <span class="field-label">意图标识</span>
                  <input v-model="addForm.intent" class="input mono" placeholder="如 light_on" />
                </label>
                <label class="field">
                  <span class="field-label">设备类型（可选）</span>
                  <input v-model="addForm.device_type" class="input mono" placeholder="light / ac / curtain" />
                </label>
              </div>

              <label class="field">
                <span class="field-label">分类</span>
                <input v-model="addForm.category" class="input" placeholder="custom" />
              </label>

              <div class="add-note">
                <Check :size="12" />
                保存后会自动重新计算 Embedding 并写入向量库，立即参与检索。
              </div>
            </div>

            <footer class="add-foot">
              <button class="btn btn-sm" @click="addOpen = false">取消</button>
              <button class="btn btn-sm btn-primary" :disabled="addSaving" @click="addEntry">
                <Loader2 v-if="addSaving" :size="12" class="spin" />
                <Plus v-else :size="12" />
                保存并索引
              </button>
            </footer>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 17px;
}

.rag-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel);
  overflow: hidden;
}

.rag-stat.panel {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 16px 18px;
  min-width: 0;
  border: none;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
}

.rag-stat.panel + .rag-stat.panel {
  border-left: 1px solid var(--line);
}

.rag-stat-icon {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 9px;
  display: grid;
  place-items: center;
}

.rag-stat-icon.mint {
  color: var(--mint);
  background: var(--mint-soft);
}

.rag-stat-icon.indigo {
  color: var(--indigo);
  background: var(--indigo-soft);
}

.rag-stat-icon.amber {
  color: var(--amber);
  background: var(--amber-soft);
}

.rag-stat-icon.blue {
  color: #4e7a8a;
  background: rgba(78, 122, 138, 0.09);
}

.rag-stat-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.rag-stat-copy span {
  font-size: 10px;
  letter-spacing: 0.02em;
  color: var(--text-3);
}

.rag-stat-copy strong {
  font-family: var(--font-serif);
  font-size: 21px;
  font-weight: 500;
  color: var(--text);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rag-stat-copy strong.small-value {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.6;
}

.rag-stat-copy strong em {
  font-family: var(--font-sans);
  font-style: normal;
  font-size: 9.5px;
  color: var(--text-4);
  margin-left: 2px;
}

.rag-stat-note {
  margin-left: auto;
  font-size: 9.5px;
  color: var(--text-4);
  white-space: nowrap;
  align-self: flex-start;
  margin-top: 2px;
}

.rag-stat-note.warn {
  color: var(--warning);
}

.knowledge-main {
  display: grid;
  grid-template-columns: minmax(0, 1.62fr) minmax(280px, 0.72fr);
  gap: 14px;
  align-items: stretch;
}

.search-panel {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-controls {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
}

.search-input-wrap {
  flex: 1;
  min-width: 230px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 6px 0 12px;
  height: 40px;
  border-radius: 11px;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.04);
  color: var(--text-4);
  transition: border-color 0.18s ease;
}

.search-input-wrap:focus-within {
  border-color: rgba(180, 74, 38, 0.2);
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  color: var(--text);
  font-size: 12px;
}

.search-input::placeholder {
  color: var(--text-4);
}

.search-submit {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 29px;
  padding: 0 10px;
  border-radius: 8px;
  border: none;
  background: var(--mint);
  color: #fffaf5;
  font-size: 10px;
  font-weight: 600;
}

.search-submit:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.example-row {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
}

.example-label {
  font-size: 9px;
  color: var(--text-4);
  margin-right: 2px;
}

.example-chip {
  padding: 3px 7px;
  border-radius: 5px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-4);
  font-size: 9px;
  transition: all 0.15s ease;
}

.example-chip:hover {
  color: var(--mint);
  border-color: rgba(180, 74, 38, 0.2);
  background: var(--mint-soft);
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 2px;
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 9px;
  color: var(--text-4);
  font-variant-numeric: tabular-nums;
}

.result-card {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(41, 37, 36, 0.075);
  background: rgba(41, 37, 36, 0.018);
}

.result-card.knowledge {
  border-color: rgba(192, 138, 62, 0.1);
  background: rgba(192, 138, 62, 0.018);
}

.result-rank {
  flex: 0 0 20px;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--text-4);
  padding-top: 2px;
}

.result-body {
  flex: 1;
  min-width: 0;
}

.result-top {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.result-kind {
  flex: 0 0 auto;
  font-size: 7.5px;
  color: var(--indigo);
  background: var(--indigo-soft);
  padding: 1px 4px;
  border-radius: 3px;
}

.result-card.knowledge .result-kind {
  color: var(--amber);
  background: var(--amber-soft);
}

.result-text {
  flex: 1;
  font-size: 11px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-score {
  font-size: 8.5px;
  color: var(--text-4);
}

.result-bar {
  height: 2px;
  border-radius: 99px;
  background: rgba(41, 37, 36, 0.05);
  margin: 5px 0;
  overflow: hidden;
}

.result-bar span {
  display: block;
  height: 100%;
  background: color-mix(in srgb, var(--mint) 70%, transparent);
  border-radius: inherit;
}

.result-card.knowledge .result-bar span {
  background: color-mix(in srgb, var(--amber) 70%, transparent);
}

.result-answer {
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--text-3);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-meta {
  font-size: 8.5px;
  color: var(--text-4);
  font-family: var(--font-mono);
}

.result-meta em {
  font-style: normal;
  color: var(--text-3);
}

.pipeline-panel {
  padding: 20px;
  display: flex;
  flex-direction: column;
}

.pipeline {
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
  padding-left: 4px;
}

.pipeline li {
  display: flex;
  gap: 11px;
  position: relative;
}

.pipeline li:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 11px;
  top: 24px;
  bottom: -14px;
  width: 1px;
  background: linear-gradient(180deg, rgba(180, 74, 38, 0.18), rgba(41, 37, 36, 0.06));
}

.pipeline-index {
  width: 23px;
  height: 23px;
  flex: 0 0 23px;
  border-radius: 7px;
  display: grid;
  place-items: center;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--mint);
  background: var(--mint-soft);
  border: 1px solid rgba(180, 74, 38, 0.13);
}

.pipeline-title {
  font-size: 10.5px;
  color: var(--text-2);
  font-weight: 500;
}

.pipeline-desc {
  font-size: 9px;
  color: var(--text-4);
  line-height: 1.5;
  margin-top: 1px;
}

.pipeline-foot {
  margin-top: auto;
  padding-top: 13px;
  border-top: 1px solid var(--line);
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 8.5px;
  line-height: 1.5;
  color: var(--text-4);
}

.pipeline-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--mint);
  margin-top: 4px;
  flex: 0 0 4px;
}

.entries-panel {
  padding: 20px;
}

.entries-filters {
  display: flex;
  align-items: center;
  gap: 8px;
}

.entries-search {
  display: flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 9px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: rgba(41, 37, 36, 0.05);
  color: var(--text-4);
}

.entries-search input {
  width: 110px;
  border: none;
  background: transparent;
  outline: none;
  color: var(--text);
  font-size: 10px;
}

.entry-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 32px;
  font-size: 11px;
  color: var(--text-3);
}

.entry-table {
  display: flex;
  flex-direction: column;
}

.entry-row {
  display: grid;
  grid-template-columns: 48px minmax(0, 2.6fr) minmax(90px, 1fr) 72px;
  gap: 10px;
  align-items: center;
  padding: 7px 6px;
  border-bottom: 1px solid rgba(41, 37, 36, 0.05);
  font-size: 10px;
  min-width: 0;
}

.entry-row:hover:not(.entry-header) {
  background: rgba(41, 37, 36, 0.018);
}

.entry-header {
  font-size: 8.5px;
  color: var(--text-4);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  border-bottom-color: var(--line);
}

.entry-kind {
  font-size: 7.5px;
  color: var(--indigo);
  background: var(--indigo-soft);
  padding: 1px 4px;
  border-radius: 3px;
  justify-self: start;
}

.entry-kind.knowledge {
  color: var(--amber);
  background: var(--amber-soft);
}

.entry-text {
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entry-intent {
  color: var(--text-4);
  font-size: 8.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entry-source {
  justify-self: start;
}

.entry-foot {
  padding-top: 9px;
  font-size: 8.5px;
  color: var(--text-4);
  text-align: center;
}

.add-backdrop {
  position: fixed;
  inset: 0;
  z-index: 340;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(33, 29, 25, 0.34);
  backdrop-filter: blur(8px);
}

.add-panel {
  width: min(540px, 100%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 18px;
  border: 1px solid var(--line-strong);
  background: #f7f2ea;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.add-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 13px;
  border-bottom: 1px solid var(--line);
}

.add-head h3 {
  font-size: 17px;
}

.add-body {
  padding: 15px 20px;
  display: flex;
  flex-direction: column;
  gap: 11px;
  overflow-y: auto;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
}

.add-note {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 9px;
  line-height: 1.6;
  color: var(--mint);
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--mint-soft);
  border: 1px solid rgba(180, 74, 38, 0.12);
}

.add-note svg {
  flex: 0 0 auto;
  margin-top: 1px;
}

.add-foot {
  display: flex;
  justify-content: flex-end;
  gap: 7px;
  padding: 13px 20px;
  border-top: 1px solid var(--line);
}

.spin {
  animation: spin 0.9s linear infinite;
}

@media (max-width: 1100px) {
  .knowledge-main {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 900px) {
  .rag-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .rag-stats {
    gap: 8px;
  }

  .rag-stat {
    padding: 10px;
  }

  .entries-filters {
    flex-direction: column;
    align-items: flex-end;
  }

  .entry-row {
    grid-template-columns: 44px minmax(0, 1fr) 60px;
  }

  .entry-intent {
    display: none;
  }

  .add-backdrop {
    padding: 0;
  }

  .add-panel {
    width: 100%;
    max-height: 100dvh;
    height: 100dvh;
    border-radius: 0;
    border: none;
  }

  .field-row {
    grid-template-columns: 1fr;
  }
}
</style>
