'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Plus, Sparkles, Play, Trash2 } from 'lucide-react'
import { api, type Topic, type Channel, TOPIC_STATUS_RU } from '@/lib/api'
import { formatDate } from '@/lib/utils'

const STATUS_COLORS: Record<Topic['status'], string> = {
  pending:     'bg-zinc-800 text-zinc-400',
  in_progress: 'bg-blue-950 text-blue-300',
  done:        'bg-green-950 text-green-400',
  failed:      'bg-red-950 text-red-400',
  skipped:     'bg-yellow-950 text-yellow-400',
}

export default function TopicsPage() {
  const qc = useQueryClient()
  const [filterStatus, setFilterStatus] = useState<Topic['status'] | ''>('')
  const [filterChannel, setFilterChannel] = useState<number | ''>('')
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [showAiDialog, setShowAiDialog] = useState(false)
  const [aiTopics, setAiTopics] = useState<Topic[]>([])
  const [newTitle, setNewTitle] = useState('')
  const [newBrief, setNewBrief] = useState('')
  const [newChannel, setNewChannel] = useState<number | ''>('')

  const { data: channels } = useQuery({ queryKey: ['channels'], queryFn: api.getChannels })
  const { data: topics, isLoading } = useQuery({
    queryKey: ['topics', filterStatus, filterChannel],
    queryFn: () => api.getTopics({
      ...(filterStatus ? { status: filterStatus } : {}),
      ...(filterChannel ? { channel_id: filterChannel as number } : {}),
      limit: 100,
    }),
  })

  const createMutation = useMutation({
    mutationFn: () => api.createTopic({ title: newTitle, brief: newBrief || undefined, channel_id: newChannel as number }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topics'] })
      toast.success('Тема добавлена')
      setShowAddDialog(false)
      setNewTitle('')
      setNewBrief('')
    },
    onError: () => toast.error('Ошибка при создании темы'),
  })

  const runMutation = useMutation({
    mutationFn: (id: number) => api.runTopic(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['topics'] }); toast.success('Запущено') },
    onError: () => toast.error('Ошибка запуска'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteTopic(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['topics'] }); toast.success('Удалено') },
    onError: () => toast.error('Ошибка удаления'),
  })

  const generateMutation = useMutation({
    mutationFn: (channelId: number) => api.generateTopics(channelId),
    onSuccess: (data) => { setAiTopics(data); toast.success(`Сгенерировано ${data.length} тем`) },
    onError: () => toast.error('Ошибка генерации'),
  })

  const bulkSaveMutation = useMutation({
    mutationFn: () => api.createTopics(aiTopics.map(t => ({ title: t.title, channel_id: t.channel_id }))),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topics'] })
      toast.success('Темы сохранены')
      setShowAiDialog(false)
      setAiTopics([])
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="section-label">Контент</div>
          <h1 className="font-display text-3xl font-bold">Темы</h1>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowAiDialog(true)}
            className="flex items-center gap-2 rounded-pill border px-4 py-2.5 text-sm font-medium transition-colors"
            style={{borderColor:'rgba(139,92,246,0.4)', background:'rgba(139,92,246,0.1)', color:'rgb(167,139,250)'}}>
            <Sparkles className="h-4 w-4" /> AI-генерация
          </button>
          <button onClick={() => setShowAddDialog(true)}
            className="flex items-center gap-2 rounded-pill bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity">
            <Plus className="h-4 w-4" /> Добавить
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <select className="rounded-pill border border-border bg-secondary text-foreground px-4 py-2 text-sm font-mono-label focus:outline-none focus:ring-1 focus:ring-primary"
          value={filterChannel} onChange={e => setFilterChannel(e.target.value ? Number(e.target.value) : '')}>
          <option value="">— Все каналы —</option>
          {channels?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select className="rounded-pill border border-border bg-secondary text-foreground px-4 py-2 text-sm font-mono-label focus:outline-none focus:ring-1 focus:ring-primary"
          value={filterStatus} onChange={e => setFilterStatus(e.target.value as Topic['status'] | '')}>
          <option value="">Все статусы</option>
          <option value="">— Все статусы —</option>
          <option value="pending">В очереди</option>
          <option value="in_progress">Генерируется</option>
          <option value="done">Готово</option>
          <option value="failed">Ошибка</option>
          <option value="skipped">Пропущено</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-lg border overflow-hidden">
        <table className="w-full text-sm table-fixed">
          <colgroup>
            <col className="w-auto" />
            <col style={{width:'110px'}} />
            <col style={{width:'80px'}} />
            <col style={{width:'130px'}} />
            <col style={{width:'130px'}} />
            <col style={{width:'72px'}} />
          </colgroup>
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-5 py-3 text-left font-mono-label text-muted-foreground">Тема</th>
              <th className="px-4 py-3 text-left font-mono-label text-muted-foreground">Статус</th>
              <th className="px-4 py-3 text-left font-mono-label text-muted-foreground">Приор.</th>
              <th className="px-4 py-3 text-left font-mono-label text-muted-foreground">Запуск</th>
              <th className="px-4 py-3 text-left font-mono-label text-muted-foreground">Создано</th>
              <th className="px-2 py-3" />
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-5 py-8 text-center font-mono-label text-muted-foreground">Загрузка...</td></tr>
            )}
            {!isLoading && (topics ?? []).length === 0 && (
              <tr><td colSpan={6} className="px-5 py-8 text-center font-mono-label text-muted-foreground">Нет тем</td></tr>
            )}
            {(topics ?? []).map(t => (
              <tr key={t.id} className="border-b border-border last:border-0 hover:bg-accent/20 transition-colors">
                <td className="px-5 py-3 min-w-0">
                  <p className="font-medium text-foreground truncate text-sm">{t.title}</p>
                  {t.brief && <p className="text-xs text-muted-foreground truncate mt-0.5">{t.brief}</p>}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[t.status]}`}>
                    {TOPIC_STATUS_RU[t.status] ?? t.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground text-xs font-mono">{t.priority}</td>
                <td className="px-4 py-3 text-muted-foreground font-mono-label">{formatDate(t.scheduled_at)}</td>
                <td className="px-4 py-3 text-muted-foreground font-mono-label">{formatDate(t.created_at)}</td>
                <td className="px-2 py-3">
                  <div className="flex gap-1">
                    {(t.status === 'pending' || t.status === 'failed') && (
                      <button onClick={() => runMutation.mutate(t.id)} title="Запустить"
                        className="rounded-lg p-1.5 text-green-400 hover:bg-green-950 transition-colors">
                        <Play className="h-3.5 w-3.5" />
                      </button>
                    )}
                    <button onClick={() => { if (confirm('Удалить тему?')) deleteMutation.mutate(t.id) }} title="Удалить"
                      className="rounded-lg p-1.5 text-red-400 hover:bg-red-950 transition-colors">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add Dialog */}
      {showAddDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={() => setShowAddDialog(false)}>
          <div className="w-full max-w-md rounded-2xl bg-card border border-border p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display text-base font-bold">Новая тема</h2>
              <button onClick={() => setShowAddDialog(false)} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
            </div>
            <div className="space-y-3">
              <select className="w-full rounded-lg border border-border bg-secondary text-foreground px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                value={newChannel} onChange={e => setNewChannel(Number(e.target.value))}>
                <option value="">Выберите канал</option>
                {channels?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <input className="w-full rounded-lg border border-border bg-secondary text-foreground px-4 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Заголовок темы" value={newTitle} onChange={e => setNewTitle(e.target.value)} />
              <textarea className="w-full rounded-lg border border-border bg-secondary text-foreground px-4 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Контекст (опционально)" rows={3} value={newBrief} onChange={e => setNewBrief(e.target.value)} />
            </div>
            <div className="mt-5 flex gap-3 justify-end">
              <button onClick={() => setShowAddDialog(false)} className="rounded-pill border border-border bg-secondary px-4 py-2 text-sm text-foreground hover:bg-accent transition-colors">Отмена</button>
              <button onClick={() => createMutation.mutate()} disabled={!newTitle || !newChannel || createMutation.isPending}
                className="rounded-pill bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50">
                Создать
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AI Dialog */}
      {showAiDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={() => { setShowAiDialog(false); setAiTopics([]) }}>
          <div className="w-full max-w-2xl rounded-2xl bg-card border border-border p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display text-base font-bold">AI-генерация тем</h2>
              <button onClick={() => { setShowAiDialog(false); setAiTopics([]) }} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
            </div>
            {aiTopics.length === 0 ? (
              <div className="space-y-3">
                <select className="w-full rounded-lg border border-border bg-secondary text-foreground px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  value={newChannel} onChange={e => setNewChannel(Number(e.target.value))}>
                  <option value="">Выберите канал</option>
                  {channels?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <div className="flex gap-2">
                  <button onClick={() => newChannel && generateMutation.mutate(newChannel as number)}
                    disabled={!newChannel || generateMutation.isPending}
                    className="flex items-center gap-2 rounded-pill px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 transition-opacity"
                    style={{background:'rgb(124,58,237)'}}>
                    <Sparkles className="h-4 w-4" />
                    {generateMutation.isPending ? 'Генерирую...' : 'Сгенерировать 20 тем'}
                  </button>
                  <button onClick={() => { setShowAiDialog(false); setAiTopics([]) }}
                    className="rounded-pill border border-border bg-secondary px-4 py-2.5 text-sm text-foreground hover:bg-accent transition-colors">Отмена</button>
                </div>
              </div>
            ) : (
              <div>
                <div className="max-h-80 overflow-y-auto space-y-2 mb-4">
                  {aiTopics.map((t, i) => (
                    <div key={i} className="flex gap-2 items-center">
                      <input className="flex-1 rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                        value={t.title} onChange={e => setAiTopics(prev => prev.map((x, j) => j === i ? { ...x, title: e.target.value } : x))}
                      />
                      <button onClick={() => setAiTopics(prev => prev.filter((_, j) => j !== i))}
                        className="text-red-400 hover:text-red-300 p-1 rounded transition-colors">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="flex gap-3 justify-end mt-4">
                  <button onClick={() => { setShowAiDialog(false); setAiTopics([]) }}
                    className="rounded-pill border border-border bg-secondary px-4 py-2 text-sm text-foreground hover:bg-accent transition-colors">Отмена</button>
                  <button onClick={() => bulkSaveMutation.mutate()} disabled={bulkSaveMutation.isPending}
                    className="rounded-pill bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50">
                    Сохранить {aiTopics.length} тем
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
