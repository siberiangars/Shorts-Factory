'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSession } from 'next-auth/react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { formatCost, formatDate } from '@/lib/utils'
import { CheckCircle2, XCircle, ExternalLink, Plus, Trash2, Copy, KeyRound, Users, Link2, TrendingUp } from 'lucide-react'

const API_KEYS = [
  { label: 'Anthropic Claude',  env: 'ANTHROPIC_API_KEY',  url: 'https://console.anthropic.com', desc: 'Генерация скриптов' },
  { label: 'ElevenLabs TTS',    env: 'ELEVENLABS_API_KEY', url: 'https://elevenlabs.io',         desc: 'Озвучка (B-roll режим)' },
  { label: 'Pexels B-roll',     env: 'PEXELS_API_KEY',     url: 'https://pexels.com/api',        desc: 'Стоковое видео (запасной)' },
  { label: 'Pixabay B-roll',    env: 'PIXABAY_API_KEY',    url: 'https://pixabay.com/api/docs',  desc: 'Медицинский сток' },
  { label: 'HeyGen Аватар',     env: 'HEYGEN_API_KEY',     url: 'https://heygen.com',            desc: 'Talking head аватар' },
  { label: 'Groq Whisper',      env: 'GROQ_API_KEY',       url: 'https://console.groq.com',      desc: 'Транскрипция (~3 сек)' },
]

const VIDEO_PIPELINE = [
  { step: '1', name: 'Скрипт', tool: 'Claude Sonnet 4.5', time: '~25 сек', cost: '~$0.02' },
  { step: '2', name: 'Озвучка', tool: 'ElevenLabs', time: '~15 сек', cost: '~$0.01' },
  { step: '3', name: 'B-roll',      tool: 'Pexels / Storyblocks',  time: '~20 сек', cost: 'free'   },
  { step: '4', name: 'Транскрипция', tool: 'Groq Whisper', time: '~3 сек', cost: 'free' },
  { step: '5', name: 'Монтаж', tool: 'FFmpeg', time: '~60 сек', cost: 'free' },
  { step: '6', name: 'YouTube', tool: 'YouTube Data API', time: '~30 сек', cost: 'free' },
]

const ADMIN_EMAILS = (process.env.NEXT_PUBLIC_ADMIN_EMAILS || '').split(',').map(s => s.trim()).filter(Boolean)

export default function SettingsPage() {
  const { data: session } = useSession()
  const qc = useQueryClient()
  const [newNote, setNewNote] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  const userEmail = (session?.user as any)?.email || session?.user?.email || ''
  const isAdmin   = (session?.user as any)?.licenseValid && ADMIN_EMAILS.includes(userEmail)

  const { data: stats }    = useQuery({ queryKey: ['stats'],    queryFn: api.getStats })
  const { data: channels } = useQuery({ queryKey: ['channels'], queryFn: api.getChannels })
  const { data: videos }   = useQuery({ queryKey: ['videos', ''], queryFn: () => api.getVideos({ limit: 200 }) })
  const { data: licenses } = useQuery({ queryKey: ['licenses'], queryFn: api.getLicenses, enabled: true })

  const createMutation = useMutation({
    mutationFn: () => api.createLicense({ note: newNote || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['licenses'] })
      setNewNote('')
      setShowCreate(false)
      toast.success('Ключ создан')
    },
    onError: () => toast.error('Ошибка создания'),
  })

  const revokeMutation = useMutation({
    mutationFn: (id: number) => api.revokeLicense(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['licenses'] }); toast.success('Лицензия отозвана') },
    onError: () => toast.error('Ошибка'),
  })

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key)
    toast.success('Ключ скопирован')
  }

  const totalCost = videos?.reduce((sum, v) => sum + parseFloat(v.generation_cost_usd || '0'), 0) ?? 0
  const doneCount = videos?.filter(v => v.status === 'done').length ?? 0
  const avgCost = doneCount > 0 ? totalCost / doneCount : 0

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Настройки</h1>

      {/* Stats summary */}
      <div className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">📊 Статистика</h2>
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Всего видео', value: (stats?.done_total ?? 0) + (stats?.pending ?? 0) },
            { label: 'Готово', value: stats?.done_total ?? 0, color: 'text-green-400' },
            { label: 'Сегодня', value: stats?.done_today ?? 0, color: 'text-blue-400' },
            { label: 'Средняя стоимость', value: formatCost(stats?.avg_cost_usd ?? null) },
          ].map(s => (
            <div key={s.label} className="text-center">
              <p className={`text-2xl font-bold ${s.color ?? ''}`}>{s.value}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
        {doneCount > 0 && (
          <p className="text-xs text-muted-foreground mt-4 text-center">
            Потрачено всего: <span className="text-foreground font-medium">{formatCost(totalCost.toFixed(4))}</span> на {doneCount} видео
          </p>
        )}
      </div>

      {/* Channels */}
      <div className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">📺 Каналы</h2>
        <div className="space-y-3">
          {(channels ?? []).map(ch => (
            <div key={ch.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
              <div>
                <p className="text-sm font-medium">{ch.name}</p>
                <p className="text-xs text-muted-foreground">{ch.niche} · {ch.language.toUpperCase()} · {(ch as any).avatar_mode === 'heygen' ? 'HeyGen' : 'B-roll'}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground">{ch.daily_upload_count}/6 сегодня</span>
                {ch.has_oauth
                  ? <span className="flex items-center gap-1 text-xs text-green-400"><CheckCircle2 className="h-3.5 w-3.5" />YouTube</span>
                  : <a href="/channels" className="flex items-center gap-1 text-xs text-red-400 hover:underline"><XCircle className="h-3.5 w-3.5" />Подключить YouTube</a>}
              </div>
            </div>
          ))}
          {(!channels || channels.length === 0) && (
            <p className="text-sm text-muted-foreground">Нет каналов. <a href="/channels" className="text-primary underline">Создать →</a></p>
          )}
        </div>
      </div>

      {/* Pipeline */}
      <div className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">⚙️ Пайплайн (~3 мин/видео)</h2>
        <div className="space-y-2">
          {VIDEO_PIPELINE.map(s => (
            <div key={s.step} className="flex items-center gap-3 py-1.5 border-b border-border/50 last:border-0">
              <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center font-bold flex-shrink-0">{s.step}</span>
              <span className="text-sm font-medium w-28">{s.name}</span>
              <span className="text-xs text-muted-foreground flex-1">{s.tool}</span>
              <span className="text-xs text-muted-foreground w-16 text-right">{s.time}</span>
              <span className="text-xs font-mono w-16 text-right text-amber-400">{s.cost}</span>
            </div>
          ))}
          <p className="text-xs text-muted-foreground pt-2">
            Итого на видео: <span className="text-foreground font-medium">~$0.03–0.05</span> (скрипт + голос; B-roll бесплатно)
          </p>
        </div>
      </div>

      {/* Лицензии */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
              <KeyRound className="h-3.5 w-3.5" /> Лицензии
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Управление доступом пользователей
            </p>
          </div>
          <button
            onClick={() => setShowCreate(v => !v)}
            className="flex items-center gap-1.5 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary px-3 py-1.5 text-xs font-medium transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> Создать ключ
          </button>
        </div>

        {/* Форма создания */}
        {showCreate && (
          <div className="px-5 py-4 border-b border-border bg-muted/20 flex gap-2">
            <input
              type="text"
              value={newNote}
              onChange={e => setNewNote(e.target.value)}
              placeholder="Заметка (кому выдаёте)"
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
            <button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending}
              className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {createMutation.isPending ? 'Создаю...' : 'Создать'}
            </button>
          </div>
        )}

        {/* Список лицензий */}
        {(!licenses || licenses.length === 0) ? (
          <div className="px-5 py-8 text-center text-sm text-muted-foreground">
            Нет лицензий. Создайте первую.
          </div>
        ) : (
          licenses.map(lic => (
            <div key={lic.id} className={`flex items-center gap-3 px-5 py-3 border-b border-border/50 last:border-0 ${!lic.is_active ? 'opacity-50' : ''}`}>
              {/* Статус */}
              {lic.is_valid
                ? <CheckCircle2 className="h-4 w-4 text-green-400 shrink-0" />
                : <XCircle className="h-4 w-4 text-red-400 shrink-0" />}

              {/* Ключ */}
              <code className="text-xs font-mono text-foreground bg-muted px-2 py-1 rounded w-36 shrink-0">
                {lic.key}
              </code>

              {/* Инфо */}
              <div className="flex-1 min-w-0">
                {lic.note && <p className="text-xs font-medium truncate">{lic.note}</p>}
                {lic.activated_by_email
                  ? <p className="text-xs text-green-400 truncate">✓ {lic.activated_by_email}</p>
                  : <p className="text-xs text-muted-foreground">Не активирован</p>}
              </div>

              <span className="text-xs text-muted-foreground shrink-0">{formatDate(lic.created_at)}</span>

              {/* Кнопки */}
              <button onClick={() => copyKey(lic.key)} className="text-muted-foreground hover:text-primary p-1" title="Скопировать">
                <Copy className="h-3.5 w-3.5" />
              </button>
              {lic.is_active && (
                <button
                  onClick={() => { if (confirm('Отозвать лицензию?')) revokeMutation.mutate(lic.id) }}
                  className="text-muted-foreground hover:text-red-400 p-1" title="Отозвать"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {/* Партнёрская программа */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
            <Users className="h-3.5 w-3.5" /> Партнёрская программа
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Продавай доступ к Shorts Factory другим пользователям
          </p>
        </div>

        {/* Статистика */}
        <div className="px-5 py-4 border-b border-border grid grid-cols-3 gap-4">
          {[
            { label: 'Всего ключей',   value: licenses?.length ?? 0,                          color: '' },
            { label: 'Активировано',   value: licenses?.filter(l => l.activated_by_email).length ?? 0, color: 'text-green-400' },
            { label: 'Свободно',       value: licenses?.filter(l => !l.activated_by_email && l.is_active).length ?? 0, color: 'text-blue-400' },
          ].map(s => (
            <div key={s.label} className="text-center">
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Ссылка для приглашения */}
        <div className="px-5 py-4 border-b border-border">
          <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
            <Link2 className="h-3.5 w-3.5" /> Ссылка для новых пользователей
          </p>
          <div className="flex gap-2">
            <code className="flex-1 bg-muted rounded-lg px-3 py-2 text-xs font-mono text-foreground truncate">
              http://shorts.v3techbots.online/activate
            </code>
            <button
              onClick={() => { navigator.clipboard.writeText('http://shorts.v3techbots.online/activate'); toast.success('Ссылка скопирована') }}
              className="flex items-center gap-1.5 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary px-3 py-2 text-xs font-medium transition-colors shrink-0"
            >
              <Copy className="h-3.5 w-3.5" /> Копировать
            </button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Пользователь переходит по ссылке, входит через Google, вводит ключ — и получает доступ.
          </p>
        </div>

        {/* Схема монетизации */}
        <div className="px-5 py-4">
          <p className="text-xs font-medium text-muted-foreground mb-3 flex items-center gap-1.5">
            <TrendingUp className="h-3.5 w-3.5" /> Схема заработка
          </p>
          <div className="space-y-2">
            {[
              { step: '1', text: 'Создай ключ лицензии в блоке выше', sub: 'SF-XXXX-XXXX-XXXX — уникальный ключ доступа' },
              { step: '2', text: 'Продай доступ клиенту', sub: 'Рекомендуемая цена: $29–99/мес за аккаунт' },
              { step: '3', text: 'Отправь ключ + ссылку на активацию', sub: 'Клиент сам активирует через Google-аккаунт' },
              { step: '4', text: 'Управляй доступом — отзывай при необходимости', sub: 'Одна кнопка — и доступ заблокирован' },
            ].map(s => (
              <div key={s.step} className="flex gap-3 py-1.5">
                <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-[10px] flex items-center justify-center font-bold shrink-0 mt-0.5">{s.step}</span>
                <div>
                  <p className="text-sm font-medium">{s.text}</p>
                  <p className="text-xs text-muted-foreground">{s.sub}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* API Keys */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">🔑 API-ключи</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Управляются через <code className="bg-muted px-1 rounded text-xs">.env</code> на сервере.
            SSH: <code className="bg-muted px-1 rounded text-xs">nano /root/shorts-factory/.env</code> → restart
          </p>
        </div>
        {API_KEYS.map(k => (
          <div key={k.env} className="flex items-center gap-4 px-5 py-3 border-b border-border/50 last:border-0 hover:bg-muted/20">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{k.label}</p>
              <p className="text-xs text-muted-foreground">{k.desc}</p>
            </div>
            <code className="text-xs font-mono text-muted-foreground bg-muted px-2 py-1 rounded">{k.env}</code>
            <a href={k.url} target="_blank" rel="noopener noreferrer"
               className="text-muted-foreground hover:text-primary transition-colors flex-shrink-0">
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        ))}
      </div>

      {/* Server info */}
      <div className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">🖥️ Сервер</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {[
            ['Адрес', 'shorts.v3techbots.online'],
            ['API Docs', 'shorts.v3techbots.online/docs'],
            ['Инструкция', 'shorts.v3techbots.online/guide'],
            ['IP', '185.252.215.53'],
          ].map(([label, val]) => (
            <div key={label} className="flex items-center gap-2">
              <span className="text-muted-foreground w-24 flex-shrink-0">{label}:</span>
              <code className="text-xs font-mono text-foreground bg-muted px-1.5 py-0.5 rounded truncate">{val}</code>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
