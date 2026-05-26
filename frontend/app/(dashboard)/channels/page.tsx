'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Plus, Link2, CheckCircle2, XCircle, User, Film, Instagram, Trash2 } from 'lucide-react'
import { api, type Channel } from '@/lib/api'
import { formatDate } from '@/lib/utils'

const GRANDFATHER_DOCTOR_PRESET = {
  name: 'Дедушка Доктор', niche: 'биохакинг, здоровье, долголетие, медицина',
  language: 'ru', voice_id: '', avatar_mode: 'heygen' as const,
  heygen_background: '#f0ede8',
  persona_description: 'Ты — Александр Михайлович, врач-геронтолог 72 лет с 45-летним стажем. Говоришь мягко, авторитетно, с искренней заботой о здоровье слушателей.',
  default_tags: ['здоровье', 'медицина', 'врач', 'долголетие', 'shorts'],
  script_prompt_template: `Ты — сценарист YouTube Shorts от лица Александра Михайловича, опытного врача-геронтолога 72 лет.\n\nТЕМА: {topic_title}\nКОНТЕКСТ: {topic_brief}\n\nВЕРНИ СТРОГИЙ JSON {...}`,
}

const EMPTY_FORM = {
  name: '', niche: '', language: 'ru', voice_id: '',
  avatar_mode: 'broll' as 'broll' | 'heygen',
  heygen_avatar_id: '', heygen_voice_id: '', heygen_background: '#f8f5f0',
  persona_description: '', auto_publish_public: false, default_tags: [] as string[], script_prompt_template: '',
}

export default function ChannelsPage() {
  const qc = useQueryClient()
  const [showDialog, setShowDialog] = useState(false)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [tagsInput, setTagsInput] = useState('')

  const { data: channels, isLoading } = useQuery({ queryKey: ['channels'], queryFn: api.getChannels })

  const createMutation = useMutation({
    mutationFn: () => api.createChannel({ ...form, default_tags: tagsInput ? tagsInput.split(',').map(t => t.trim()).filter(Boolean) : [] }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['channels'] }); toast.success('Канал создан'); setShowDialog(false); setForm({ ...EMPTY_FORM }); setTagsInput('') },
    onError: (e: any) => toast.error(`Ошибка: ${e.response?.data?.detail ?? e.message}`),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteChannel(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['channels'] }); toast.success('Канал удалён') },
    onError: () => toast.error('Ошибка при удалении'),
  })

  const applyPreset = () => {
    setForm({ ...EMPTY_FORM, name: GRANDFATHER_DOCTOR_PRESET.name, niche: GRANDFATHER_DOCTOR_PRESET.niche, language: GRANDFATHER_DOCTOR_PRESET.language, avatar_mode: GRANDFATHER_DOCTOR_PRESET.avatar_mode, heygen_background: GRANDFATHER_DOCTOR_PRESET.heygen_background, persona_description: GRANDFATHER_DOCTOR_PRESET.persona_description, script_prompt_template: GRANDFATHER_DOCTOR_PRESET.script_prompt_template })
    setTagsInput(GRANDFATHER_DOCTOR_PRESET.default_tags.join(', '))
    toast.info('Пресет применён')
  }

  const connectYoutube = async (id: number) => {
    try { const { auth_url } = await api.getAuthUrl(id); window.location.href = auth_url }
    catch { toast.error('Ошибка YouTube OAuth') }
  }
  const connectInstagram = async (id: number) => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/instagram/${id}/auth-url`, { headers: { Authorization: `Bearer ${process.env.NEXT_PUBLIC_API_TOKEN ?? ''}` } })
      if (!res.ok) { const e = await res.json(); toast.error(`Instagram: ${e.detail}`); return }
      const { auth_url } = await res.json(); window.location.href = auth_url
    } catch { toast.error('Ошибка Instagram OAuth') }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="section-label">Управление</div>
          <h1 className="font-display text-3xl font-bold">Каналы</h1>
        </div>
        <button onClick={() => setShowDialog(true)}
          className="flex items-center gap-2 rounded-pill bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity">
          <Plus className="h-4 w-4" /> Создать канал
        </button>
      </div>

      {isLoading && <p className="font-mono-label text-muted-foreground">Загрузка...</p>}

      {!isLoading && (channels ?? []).length === 0 && (
        <div className="rounded-xl border border-border bg-card p-16 text-center">
          <p className="font-display text-sm text-muted-foreground">Нет каналов</p>
          <p className="text-xs text-muted-foreground mt-2">Создайте первый канал для начала работы</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        {(channels ?? []).map(ch => (
          <div key={ch.id} className="rounded-xl border border-border bg-card p-6 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  {(ch as any).avatar_mode === 'heygen' ? (
                    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-violet-950 text-violet-300">
                      <User className="h-3 w-3" /> HeyGen
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-blue-950 text-blue-300">
                      <Film className="h-3 w-3" /> B-roll
                    </span>
                  )}
                </div>
                <h2 className="font-display text-sm font-bold truncate">{ch.name}</h2>
                <p className="text-xs text-muted-foreground truncate mt-0.5">{ch.niche}</p>
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                {ch.has_oauth
                  ? <span className="flex items-center gap-1 text-xs text-green-400"><CheckCircle2 className="h-3.5 w-3.5" /> YouTube</span>
                  : <span className="flex items-center gap-1 text-xs text-red-400"><XCircle className="h-3.5 w-3.5" /> YouTube</span>}
                {(ch as any).has_instagram
                  ? <span className="flex items-center gap-1 text-xs text-green-400"><CheckCircle2 className="h-3.5 w-3.5" /> Instagram</span>
                  : <span className="flex items-center gap-1 text-xs text-muted-foreground"><XCircle className="h-3.5 w-3.5" /> Instagram</span>}
                <button
                  onClick={() => { if (confirm(`Удалить канал "${ch.name}"?`)) deleteMutation.mutate(ch.id) }}
                  disabled={deleteMutation.isPending}
                  className="mt-1 rounded-lg p-1.5 text-red-400 hover:bg-red-950 transition-colors disabled:opacity-50"
                  title="Удалить канал"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs border-t border-border pt-4">
              <span className="text-muted-foreground">Язык</span>
              <span className="text-foreground font-mono">{ch.language}</span>
              <span className="text-muted-foreground">Квота сегодня</span>
              <span className="text-foreground font-mono">{ch.daily_upload_count} / 6</span>
              <span className="text-muted-foreground">Создан</span>
              <span className="text-foreground font-mono">{formatDate(ch.created_at)}</span>
            </div>

            <div className="flex gap-2 pt-2">
              <button onClick={() => connectYoutube(ch.id)}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-border bg-secondary px-3 py-2 text-xs text-foreground hover:bg-accent transition-colors">
                <Link2 className="h-3.5 w-3.5" />
                {ch.has_oauth ? 'YouTube ✓' : 'Подключить YouTube'}
              </button>
              <button onClick={() => connectInstagram(ch.id)}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-xs transition-colors"
                style={{borderColor:'rgba(236,72,153,0.25)', background:'rgba(236,72,153,0.05)', color:(ch as any).has_instagram ? 'rgb(249,168,212)' : 'hsl(var(--muted-foreground))'}}>
                <Instagram className="h-3.5 w-3.5" />
                {(ch as any).has_instagram ? 'Instagram ✓' : 'Подключить'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Dialog */}
      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={() => { setShowDialog(false); setForm({ ...EMPTY_FORM }); setTagsInput('') }}>
          <div className="w-full max-w-xl rounded-2xl bg-card border border-border shadow-2xl max-h-[90vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}>
            <div className="p-6 space-y-5">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-base font-bold">Новый канал</h2>
                <div className="flex items-center gap-2">
                  <button onClick={applyPreset}
                    className="flex items-center gap-1.5 rounded-pill border px-3 py-1.5 text-xs font-medium transition-colors"
                    style={{borderColor:'rgba(255,209,102,0.3)', background:'rgba(255,209,102,0.08)', color:'hsl(43 100% 70%)'}}>
                    👴 Дедушка Врач
                  </button>
                  <button onClick={() => { setShowDialog(false); setForm({ ...EMPTY_FORM }); setTagsInput('') }}
                    className="text-muted-foreground hover:text-foreground text-xl leading-none">✕</button>
                </div>
              </div>

              {/* Mode toggle */}
              <div>
                <div className="font-mono-label text-muted-foreground mb-2">Режим</div>
                <div className="flex gap-2">
                  {(['broll', 'heygen'] as const).map(mode => (
                    <button key={mode} onClick={() => setForm(f => ({ ...f, avatar_mode: mode }))}
                      className={`flex-1 flex items-center justify-center gap-2 rounded-lg border py-2.5 text-xs font-medium transition-all ${
                        form.avatar_mode === mode
                          ? mode === 'heygen'
                            ? 'bg-violet-600 text-white border-violet-600'
                            : 'bg-primary text-primary-foreground border-primary'
                          : 'bg-secondary border-border text-muted-foreground hover:text-foreground'
                      }`}>
                      {mode === 'heygen' ? <><User className="h-3.5 w-3.5" /> HeyGen</> : <><Film className="h-3.5 w-3.5" /> B-roll + Голос</>}
                    </button>
                  ))}
                </div>
              </div>

              {/* Fields */}
              <div className="space-y-3">
                {[['name','Название канала'],['niche','Ниша']].map(([f,p]) => (
                  <input key={f} className="w-full rounded-lg border border-border bg-secondary text-foreground px-4 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    placeholder={p} value={(form as any)[f]} onChange={e => setForm(prev => ({ ...prev, [f]: e.target.value }))} />
                ))}
                <select className="w-full rounded-lg border border-border bg-secondary text-foreground px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  value={form.language} onChange={e => setForm(f => ({ ...f, language: e.target.value }))}>
                  <option value="ru">Русский (ru)</option>
                  <option value="en">English (en)</option>
                </select>
                {form.avatar_mode === 'broll' && (
                  <input className="w-full rounded-lg border border-border bg-secondary text-foreground px-4 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    placeholder="ElevenLabs Voice ID" value={form.voice_id} onChange={e => setForm(f => ({ ...f, voice_id: e.target.value }))} />
                )}
                {form.avatar_mode === 'heygen' && (
                  <div className="space-y-3 rounded-xl border p-4" style={{borderColor:'rgba(139,92,246,0.25)', background:'rgba(139,92,246,0.05)'}}>
                    <div className="font-mono-label" style={{color:'rgb(167,139,250)'}}>HeyGen</div>
                    {[['heygen_avatar_id','Avatar ID'],['heygen_voice_id','Voice ID']].map(([f,p]) => (
                      <input key={f} className="w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                        placeholder={p} value={(form as any)[f]} onChange={e => setForm(prev => ({ ...prev, [f]: e.target.value }))} />
                    ))}
                    {form.persona_description && (
                      <textarea className="w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-sm leading-relaxed focus:outline-none focus:ring-1 focus:ring-primary"
                        rows={2} value={form.persona_description} onChange={e => setForm(f => ({ ...f, persona_description: e.target.value }))} />
                    )}
                  </div>
                )}
                <input className="w-full rounded-lg border border-border bg-secondary text-foreground px-4 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Теги (через запятую)" value={tagsInput} onChange={e => setTagsInput(e.target.value)} />
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <input type="checkbox" checked={form.auto_publish_public} onChange={e => setForm(f => ({ ...f, auto_publish_public: e.target.checked }))} className="accent-yellow-400" />
                  Авто-публикация (public)
                </label>
              </div>

              <div className="flex gap-3 justify-end pt-2">
                <button onClick={() => { setShowDialog(false); setForm({ ...EMPTY_FORM }); setTagsInput('') }}
                  className="rounded-pill border border-border bg-secondary px-5 py-2 text-sm text-foreground hover:bg-accent transition-colors">Отмена</button>
                <button onClick={() => createMutation.mutate()} disabled={!form.name || createMutation.isPending}
                  className="rounded-pill bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-opacity">
                  {createMutation.isPending ? 'Создаю...' : 'Создать'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
