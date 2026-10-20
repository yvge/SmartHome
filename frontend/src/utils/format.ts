export function uid(prefix = ''): string {
  const random =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID().replace(/-/g, '').slice(0, 12)
      : Math.random().toString(36).slice(2, 14)
  return `${prefix}${random}`
}

export function pad(value: number): string {
  return String(value).padStart(2, '0')
}

export function formatTime(value: string | number | Date | null | undefined): string {
  if (value === null || value === undefined) return '--:--'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '--:--'
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function formatDateTime(value: string | number | Date | null | undefined): string {
  if (value === null || value === undefined) return '--'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function relativeTime(value: string | number | Date | null | undefined): string {
  if (!value) return '--'
  const date = value instanceof Date ? value : new Date(value)
  const diff = Date.now() - date.getTime()
  if (Number.isNaN(diff)) return '--'
  if (diff < 45_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)} 天前`
  return formatDateTime(date)
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function formatWatt(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  if (value >= 1000) return `${(value / 1000).toFixed(2)} kW`
  return `${Math.round(value)} W`
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function greetingForHour(hour: number): string {
  if (hour < 5) return '夜深了'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

export function periodGreeting(period?: string): string {
  switch (period) {
    case '清晨':
      return '晨光正好'
    case '上午':
      return '上午好'
    case '正午':
      return '中午好'
    case '午后':
      return '午后惬意'
    case '傍晚':
      return '傍晚好'
    case '夜晚':
      return '晚上好'
    case '深夜':
      return '夜深了'
    default:
      return '欢迎回家'
  }
}

export function statusLabel(status?: string): string {
  const map: Record<string, string> = {
    success: '成功',
    partial: '部分完成',
    failed: '失败',
    skipped: '已跳过',
    running: '执行中',
    pending: '待执行',
    done: '已完成',
    idle: '待执行',
    blocked: '已拦截',
    fallback: '兜底完成',
    responded: '已完成',
    llm: '大模型',
    offline: '离线规则',
  }
  return map[status || ''] || status || '未知'
}

export function devicePrimaryMetric(device: { type: string; properties: Record<string, any> }): string {
  const p = device.properties
  switch (device.type) {
    case 'light':
      return p.power ? `亮度 ${p.brightness}% · ${p.color_temp}K` : '已关闭'
    case 'ac':
      return p.power ? `${p.target_temp}°C · ${acModeLabel(p.mode)}` : '已关闭'
    case 'curtain':
      return `开合度 ${p.position}%`
    case 'purifier':
      return p.power ? `PM2.5 ${p.pm25 ?? '--'} · ${purifierModeLabel(p.mode)}` : `PM2.5 ${p.pm25 ?? '--'}`
    case 'humidifier':
      return p.power ? `目标湿度 ${p.target_humidity}%` : '已关闭'
    case 'socket':
      return p.power ? `通电 · ${p.power_w ?? 0}W` : '已断电'
    case 'speaker':
      return p.playing ? `正在播放 · ${p.track}` : p.power ? `待机 · 音量 ${p.volume}%` : '已关闭'
    case 'vacuum':
      return p.power ? `清扫中 · 电量 ${p.battery}%` : `已在充电座 · ${p.battery}%`
    case 'sensor':
      return `${p.temperature}°C · ${p.humidity}%`
    default:
      return ''
  }
}

export function acModeLabel(mode?: string): string {
  return ({ cool: '制冷', heat: '制热', dry: '除湿', fan: '送风', auto: '自动' } as Record<string, string>)[
    mode || ''
  ] || mode || '--'
}

export function purifierModeLabel(mode?: string): string {
  return ({ auto: '自动', sleep: '睡眠', high: '强力' } as Record<string, string>)[mode || ''] || mode || '--'
}

export function jsonPreview(value: unknown, max = 160): string {
  try {
    const text = typeof value === 'string' ? value : JSON.stringify(value)
    return text.length > max ? `${text.slice(0, max)}…` : text
  } catch {
    return String(value)
  }
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
