'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { api, type Video, VIDEO_STATUS_RU } from '@/lib/api'
import { formatDate, formatCost } from '@/lib/utils'
import { CheckCircle2, XCircle, ExternalLink } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

const PIPELINE_STEPS = [
  { n: '1', name: 'Скрипт',       tool: 'Claude Sonnet',  time: '~25 сек',  cost: '~$0.02' },
  { n: '2', name: 'Озвучка',      tool: 'ElevenLabs',     time: '~15 сек',  cost: '~$0.20' },
  { n: '3', name: 'B-roll',       tool: 'Pexels / FLUX',  time: '~30 сек',  cost: '$0–0.02' },
  { n: '4', name: 'Транскрипция', tool: 'Groq Whisper',   time: '~3 сек',   cost: 'free' },
  { n: '5', name: 'Монтаж',       tool: 'FFmpeg',          time: '~60 сек',  cost: 'free' },
  { n: '6', name: 'YouTube',      tool: 'YouTube API',    time: '~30 сек',  cost: 'free' },
]

const API_KEYS = [
  { label: 'Anthropic',   env: 'ANTHROPIC_API_KEY',  url: 'https://console.anthropic.com' },
  { label: 'ElevenLabs',  env: 'ELEVENLABS_API_KEY', url: 'https://elevenlabs.io' },
  { label: 'Pexels',      env: 'PEXELS_API_KEY',     url: 'https://pexels.com/api' },
  { label: 'Groq',        env: 'GROQ_API_KEY',       url: 'https://console.groq.com' },
]

function StatusBadge({ status }: { status: Video['status'] }) {
  const colors: Record<Video['status'], string> = {
    pending: 'bg-zinc-800 text-zinc-400', generating_script: 'bg-blue-950 text-blue-300',
    generating_voice: 'bg-indigo-950 text-indigo-300', fetching_broll: 'bg-purple-950 text-purple-300',
    transcribing: 'bg-violet-950 text-violet-300', assembling: 'bg-amber-950 text-amber-300',
    uploading: 'bg-orange-950 text-orange-300', done: 'bg-green-950 text-green-300',
    failed: 'bg-red-950 text-red-400',
  }
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors[status]}`}>{VIDEO_STATUS_RU[status]}</span>
}

export default function DashboardPage() {
  const { data: stats } = useQuery({ queryKey: ['stats'], queryFn: api.getStats, refetchInterval: 15000 })
  const { data: videos } = useQuery({ queryKey: ['videos', ''], queryFn: () => api.getVideos({ limit: 60 }), refetchInterval: 10000 })
  const { data: channels } = useQuery({ queryKey: ['channels'], queryFn: api.getChannels })

  const recent = (videos ?? []).slice(0, 10)
  const totalCost = (videos ?? []).reduce((s, v) => s + parseFloat(v.generation_cost_usd || '0'), 0)
  const done = (videos ?? []).filter(v => v.status === 'done').length
  const active = (videos ?? []).filter(v => !['done','failed','pending'].includes(v.status))

  const chartData = (() => {
    const counts: Record<string, number> = {}
    for (let i = 29; i >= 0; i--) {
      const d = new Date(); d.setDate(d.getDate() - i)
      counts[d.toISOString().slice(0, 10)] = 0
    }
    for (const v of videos ?? []) {
      if (v.published_at) { const day = v.published_at.slice(0, 10); if (day in counts) counts[day]++ }
    }
    return Object.entries(counts).map(([date, count]) => ({ date: date.slice(5), count }))
  })()

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Дашборд</h1>

      {active.length > 0 && (
        <div className="rounded-xl border border-blue-800 bg-blue-950/30 p-4 flex items-center gap-3">
          <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-blue-300">Генерируется {active.length} видео</p>
            <p className="text-xs text-blue-400 mt-0.5">{active.map(v => (v.topic_title || `#${v.id}`).slice(0, 40)).join(' · ')}</p>
          </div>
          <Link href="/videos" className="ml-auto text-xs text-blue-400 hover:text-blue-300 underline">Смотреть →</Link>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'В очереди',       value: stats?.pending ?? 0 },
          { label: 'Сегодня',         value: stats?.done_today ?? 0, color: 'text-green-400' },
          { label: 'Всего готово',    value: stats?.done_total ?? 0, color: 'text-blue-400' },
          { label: 'Средняя стоимость', value: stats?.avg_cost_usd ? formatCost(stats.avg_cost_usd) : '—' },
        ].map(s => (
          <div key={s.label} className="rounded-xl border border-border bg-card p-5">
            <p className="text-sm text-muted-foreground">{s.label}</p>
            <p className={`mt-1 text-3xl font-bold ${(s as any).color ?? ''}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 rounded-xl border border-border bg-card p-5">
          <p className="text-sm font-medium text-muted-foreground mb-4">Публикации за 30 дней</p>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium">Каналы</p>
            <Link href="/channels" className="text-xs text-primary hover:underline">Управление →</Link>
          </div>
          <div className="space-y-3">
            {(channels ?? []).map(ch => (
              <div key={ch.id} className="flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{ch.name}</p>
                  <p className="text-xs text-muted-foreground">{ch.daily_upload_count}/6 сегодня</p>
                </div>
                <div className="flex flex-col items-end gap-0.5 ml-2 flex-shrink-0">
                  {ch.has_oauth
                    ? <span className="flex items-center gap-1 text-xs text-green-400"><CheckCircle2 className="h-3 w-3" />YT</span>
                    : <Link href="/channels" className="flex items-center gap-1 text-xs text-red-400"><XCircle className="h-3 w-3" />Подключить YT</Link>}
                </div>
              </div>
            ))}
            {(!channels || channels.length === 0) && (
              <Link href="/channels" className="text-sm text-primary hover:underline">+ Создать канал</Link>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm font-medium mb-3">⚙️ Пайплайн (~2 мин/видео)</p>
          <div className="space-y-1.5">
            {PIPELINE_STEPS.map(s => (
              <div key={s.n} className="flex items-center gap-2 text-xs">
                <span className="w-5 h-5 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold flex-shrink-0 text-[10px]">{s.n}</span>
                <span className="font-medium w-20">{s.name}</span>
                <span className="text-muted-foreground flex-1">{s.tool}</span>
                <span className="text-muted-foreground w-14 text-right">{s.time}</span>
                <span className="text-amber-400 w-14 text-right font-mono">{s.cost}</span>
              </div>
            ))}
            {done > 0 && (
              <p className="text-xs text-muted-foreground pt-2 border-t border-border mt-2">
                Потрачено всего: <span className="text-foreground">{formatCost(totalCost.toFixed(4))}</span> на {done} видео
              </p>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm font-medium mb-1">🔑 API-ключи</p>
          <p className="text-xs text-muted-foreground mb-3">
            Изменить: <code className="bg-muted px-1 rounded text-xs">nano /root/shorts-factory/.env</code>
          </p>
          <div className="space-y-2">
            {API_KEYS.map(k => (
              <div key={k.env} className="flex items-center gap-2">
                <span className="text-xs font-medium w-20">{k.label}</span>
                <code className="flex-1 text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded truncate">{k.env}</code>
                <a href={k.url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-primary flex-shrink-0">
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <p className="text-sm font-medium">Последние видео</p>
          <Link href="/videos" className="text-xs text-primary hover:underline">Все →</Link>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-5 py-2 text-left text-xs font-medium text-muted-foreground">Тема</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Статус</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Стоимость</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">Создано</th>
            </tr>
          </thead>
          <tbody>
            {recent.length === 0 && (
              <tr><td colSpan={4} className="px-5 py-6 text-center text-muted-foreground text-sm">
                Нет видео. <Link href="/topics" className="text-primary underline">Запусти тему →</Link>
              </td></tr>
            )}
            {recent.map(v => (
              <tr key={v.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                <td className="px-5 py-2.5 max-w-xs">
                  <Link href={`/videos/${v.id}`} className="font-medium truncate block hover:text-primary">
                    {v.script_title || v.topic_title || `Видео #${v.id}`}
                  </Link>
                </td>
                <td className="px-4 py-2.5"><StatusBadge status={v.status} /></td>
                <td className="px-4 py-2.5 text-muted-foreground">{formatCost(v.generation_cost_usd)}</td>
                <td className="px-4 py-2.5 text-muted-foreground text-xs">{formatDate(v.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
