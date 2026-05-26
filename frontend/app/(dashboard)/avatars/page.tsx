'use client'

import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  UserSquare2, Wand2, Mic, Upload, Trash2, Sparkles,
  Play, Loader2, CheckCircle2, RefreshCw, Plus, Copy
} from 'lucide-react'
import { api, type HeyGenAvatar, type TalkingPhoto, type HeyGenVoice } from '@/lib/api'

// ── Tabs ──────────────────────────────────────────────────────────────────────
type Tab = 'library' | 'presets' | 'create' | 'voice'

// ── Avatar presets ────────────────────────────────────────────────────────────
// Значения соответствуют HeyGen API (проверено):
// gender: Man | Woman
// age: Young Adult | Early Middle Age | Late Middle Age | Senior
// orientation: vertical | horizontal | square
// style: Realistic | Cinematic
// pose: half_body | close_up | full_body
// appearance: casual | formal | smart_casual

const AVATAR_PRESETS = [
  {
    id: 'doctor_mikhail',
    name: 'Доктор Михаил',
    emoji: '👨‍⚕️',
    desc: 'Авторитетный терапевт, вызывает доверие',
    gender: 'Man', age: 'Early Middle Age', ethnicity: 'White',
    orientation: 'vertical', style: 'Cinematic', pose: 'half_body', appearance: 'formal',
    prompt: 'A serious authoritative male doctor aged 45, intelligent piercing eyes, short dark hair with grey temples, neat professional stubble, kind but stern expression of an expert physician',
    voice: { stability: 0.65, similarity_boost: 0.75, style: 0.1, desc: 'Спокойный, авторитетный, без спешки' },
  },
  {
    id: 'nutritionist_anna',
    name: 'Нутрициолог Анна',
    emoji: '👩‍⚕️',
    desc: 'Эксперт по питанию, доброжелательная',
    gender: 'Woman', age: 'Early Middle Age', ethnicity: 'White',
    orientation: 'vertical', style: 'Cinematic', pose: 'half_body', appearance: 'smart_casual',
    prompt: 'An attractive female nutritionist aged 38, warm radiant brown eyes, genuine welcoming smile, neat professional appearance, healthy glowing skin, confident and approachable expression',
    voice: { stability: 0.55, similarity_boost: 0.80, style: 0.15, desc: 'Мягкий, тёплый, энергичный' },
  },
  {
    id: 'professor_volkov',
    name: 'Профессор Волков',
    emoji: '👨‍🔬',
    desc: 'Учёный-академик, серьёзная наука',
    gender: 'Man', age: 'Senior', ethnicity: 'White',
    orientation: 'vertical', style: 'Realistic', pose: 'half_body', appearance: 'formal',
    prompt: 'A distinguished male professor aged 62, silver-white hair swept back, sharp intellectual eyes behind thin glasses, wise academic face, calm authoritative demeanor',
    voice: { stability: 0.75, similarity_boost: 0.70, style: 0.05, desc: 'Размеренный, глубокий, академический' },
  },
  {
    id: 'biohacker_alex',
    name: 'Биохакер Алекс',
    emoji: '🧬',
    desc: 'Молодой эксперт по оптимизации',
    gender: 'Man', age: 'Young Adult', ethnicity: 'White',
    orientation: 'vertical', style: 'Cinematic', pose: 'half_body', appearance: 'smart_casual',
    prompt: 'A modern athletic male biohacker aged 30, confident sharp eyes, clean-cut appearance, energetic and focused expression, health optimization expert look, strong jawline',
    voice: { stability: 0.50, similarity_boost: 0.78, style: 0.20, desc: 'Динамичный, уверенный, современный' },
  },
  {
    id: 'doctor_elena',
    name: 'Доктор Елена',
    emoji: '👩‍💼',
    desc: 'Врач-кардиолог, заботливая и точная',
    gender: 'Woman', age: 'Early Middle Age', ethnicity: 'White',
    orientation: 'vertical', style: 'Cinematic', pose: 'half_body', appearance: 'formal',
    prompt: 'A caring female cardiologist aged 42, kind blue eyes full of compassion, calm professional face with a reassuring expression, elegant yet approachable appearance, trustworthy doctor look',
    voice: { stability: 0.60, similarity_boost: 0.80, style: 0.10, desc: 'Спокойный, заботливый, чёткий' },
  },
  {
    id: 'coach_dmitry',
    name: 'Тренер Дмитрий',
    emoji: '💪',
    desc: 'Спортивный тренер по ЗОЖ',
    gender: 'Man', age: 'Young Adult', ethnicity: 'White',
    orientation: 'vertical', style: 'Realistic', pose: 'half_body', appearance: 'casual',
    prompt: 'A fit athletic male personal trainer aged 28, strong defined jawline, bright motivated eyes, wide genuine smile, healthy athletic build, energetic motivational coach expression',
    voice: { stability: 0.45, similarity_boost: 0.82, style: 0.25, desc: 'Энергичный, мотивирующий, быстрый' },
  },
]

// ── ElevenLabs voice presets ──────────────────────────────────────────────────
const VOICE_PRESETS = [
  {
    id: 'el_deep_male',
    name: 'Глубокий мужской',
    emoji: '🔊',
    desc: 'Авторитетный, медицинский контент',
    settings: { stability: 0.70, similarity_boost: 0.75, style: 0.05, use_speaker_boost: true },
    recommended_for: 'Доктор, профессор, эксперт',
    model: 'eleven_multilingual_v2',
  },
  {
    id: 'el_warm_female',
    name: 'Тёплый женский',
    emoji: '🎙️',
    desc: 'Доброжелательный, нутрициолог, wellness',
    settings: { stability: 0.55, similarity_boost: 0.82, style: 0.15, use_speaker_boost: true },
    recommended_for: 'Нутрициолог, врач, психолог',
    model: 'eleven_multilingual_v2',
  },
  {
    id: 'el_energetic',
    name: 'Энергичный',
    emoji: '⚡',
    desc: 'Динамичный, спорт и биохакинг',
    settings: { stability: 0.45, similarity_boost: 0.80, style: 0.25, use_speaker_boost: true },
    recommended_for: 'Биохакер, тренер, фитнес',
    model: 'eleven_multilingual_v2',
  },
  {
    id: 'el_academic',
    name: 'Академический',
    emoji: '📚',
    desc: 'Медленный, чёткий, научный стиль',
    settings: { stability: 0.80, similarity_boost: 0.70, style: 0.02, use_speaker_boost: false },
    recommended_for: 'Профессор, научпоп, факты',
    model: 'eleven_multilingual_v2',
  },
]

// ── Helper: copy to clipboard ─────────────────────────────────────────────────
function copyJson(obj: object, label: string) {
  navigator.clipboard.writeText(JSON.stringify(obj, null, 2))
  toast.success(`${label} скопированы`)
}

// ── Drop zone ─────────────────────────────────────────────────────────────────
function DropZone({ accept, label, hint, icon: Icon, onFile }: {
  accept: string; label: string; hint: string
  icon: React.ElementType; onFile: (f: File) => void
}) {
  const [drag, setDrag] = useState(false)
  const ref = useRef<HTMLInputElement>(null)
  const handle = (f: File | null | undefined) => { if (f) onFile(f) }
  const onDrop = (e: React.DragEvent) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files[0]) }
  return (
    <div onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
      onDrop={onDrop} onClick={() => ref.current?.click()}
      className={`flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl p-10 cursor-pointer transition-colors
        ${drag ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50 hover:bg-muted/30'}`}>
      <Icon className="h-8 w-8 text-muted-foreground" />
      <div className="text-center">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>
      </div>
      <input ref={ref} type="file" accept={accept} className="hidden" onChange={e => handle(e.target.files?.[0])} />
    </div>
  )
}

// ── Avatar card ───────────────────────────────────────────────────────────────
function AvatarCard({ avatar, onDelete }: { avatar: any; onDelete?: () => void }) {
  const id      = avatar.avatar_id ?? avatar.talking_photo_id
  const name    = avatar.avatar_name ?? avatar.talking_photo_name
  const preview = avatar.preview_image_url
  return (
    <div className="group relative rounded-xl border border-border bg-card overflow-hidden">
      <div className="aspect-square bg-muted flex items-center justify-center overflow-hidden">
        {preview
          ? <img src={preview} alt={name} className="w-full h-full object-cover" />
          : <UserSquare2 className="h-10 w-10 text-muted-foreground" />}
      </div>
      <div className="p-3">
        <p className="text-xs font-medium truncate">{name}</p>
        <p className="text-[10px] text-muted-foreground mt-0.5">
          {avatar._isTalkingPhoto ? 'Talking Photo' : 'HeyGen'} · {String(id).slice(0, 8)}…
        </p>
      </div>
      {onDelete && (
        <button onClick={onDelete}
          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 bg-red-950 text-red-400 rounded-lg p-1.5 transition-opacity">
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}

// ── Voice card ────────────────────────────────────────────────────────────────
function VoiceCard({ v }: { v: HeyGenVoice }) {
  const [playing, setPlaying] = useState(false)
  const play = () => {
    if (!v.preview_audio) return
    const a = new Audio(v.preview_audio); setPlaying(true)
    a.play(); a.onended = () => setPlaying(false)
  }
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border/50 last:border-0 hover:bg-muted/20">
      <button onClick={play} disabled={!v.preview_audio}
        className="w-7 h-7 rounded-full bg-primary/20 text-primary flex items-center justify-center hover:bg-primary/30 disabled:opacity-40 shrink-0">
        {playing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3 w-3 ml-0.5" />}
      </button>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{v.name}</p>
        <p className="text-xs text-muted-foreground">{v.language} · {v.gender}</p>
      </div>
      <code className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{v.voice_id.slice(0, 12)}…</code>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function AvatarsPage() {
  const [tab, setTab] = useState<Tab>('presets')
  const qc = useQueryClient()

  const { data: avatars, isLoading: loadA } = useQuery({ queryKey: ['heygen-avatars'],  queryFn: api.getHeyGenAvatars  })
  const { data: photos,  isLoading: loadP } = useQuery({ queryKey: ['talking-photos'],  queryFn: api.getTalkingPhotos  })
  const { data: voices,  isLoading: loadV } = useQuery({ queryKey: ['heygen-voices'],   queryFn: api.getHeyGenVoices   })

  // Create from photo
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [photoName, setPhotoName] = useState('')
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)

  // Generate from prompt
  const [mode,       setMode]       = useState<'upload' | 'prompt'>('upload')
  const [prompt,     setPrompt]     = useState('')
  const [promptName, setPromptName] = useState('')
  const [gender,     setGender]     = useState('male')
  const [age,        setAge]        = useState('middle_aged')

  // Voice
  const [voiceFile, setVoiceFile] = useState<File | null>(null)
  const [voiceName, setVoiceName] = useState('')
  const [recording, setRecording] = useState(false)
  const mediaRef  = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  // Creating preset
  const [creatingPreset, setCreatingPreset] = useState<string | null>(null)

  const handlePhotoSelect = (f: File) => {
    setPhotoFile(f); setPhotoPreview(URL.createObjectURL(f))
    if (!photoName) setPhotoName(f.name.replace(/\.[^.]+$/, ''))
  }

  // Mutations
  const createFromPhoto = useMutation({
    mutationFn: async () => {
      if (!photoFile || !photoName) throw new Error('Выбери фото и введи имя')
      const asset = await api.uploadAsset(photoFile)
      return api.createTalkingPhoto({ name: photoName, image_key: asset.image_key })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['talking-photos'] })
      toast.success('Аватар создан!'); setPhotoFile(null); setPhotoPreview(null); setPhotoName(''); setTab('library')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || e.message),
  })

  const generateFromPrompt = useMutation({
    mutationFn: (vars?: { name?: string; p?: string; g?: string; a?: string }) =>
      api.generateAiAvatar({
        name:   (vars?.name  ?? promptName) || 'AI Аватар',
        prompt: (vars?.p    ?? prompt),
        gender: (vars?.g    ?? gender),
        age:    (vars?.a    ?? age),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['heygen-avatars'] })
      toast.success('Генерирую аватар — появится в библиотеке через 1-2 мин')
      setPrompt(''); setPromptName(''); setCreatingPreset(null); setTab('library')
    },
    onError: (e: any) => { toast.error(e.response?.data?.detail || e.message); setCreatingPreset(null) },
  })

  const createPreset = (preset: typeof AVATAR_PRESETS[0]) => {
    setCreatingPreset(preset.id)
    api.generateAiAvatar({
      name:        preset.name,
      prompt:      preset.prompt,
      gender:      preset.gender,
      age:         preset.age,
      ethnicity:   preset.ethnicity,
      orientation: preset.orientation,
      style:       preset.style,
      pose:        preset.pose,
      appearance:  preset.appearance,
    }).then(() => {
      qc.invalidateQueries({ queryKey: ['heygen-avatars'] })
      toast.success(`${preset.name} — генерируется, появится в Библиотеке через 1-2 мин`)
      setCreatingPreset(null)
      setTab('library')
    }).catch((e: any) => {
      toast.error(e.response?.data?.detail || e.message)
      setCreatingPreset(null)
    })
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteTalkingPhoto(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['talking-photos'] }); toast.success('Удалено') },
  })

  const cloneVoice = useMutation({
    mutationFn: () => {
      if (!voiceFile || !voiceName) throw new Error('Загрузи аудио и введи имя')
      return api.cloneVoice(voiceName, voiceFile)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['heygen-voices'] })
      toast.success('Голос клонирован!'); setVoiceFile(null); setVoiceName('')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || e.message),
  })

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream); chunksRef.current = []
      mr.ondataavailable = e => chunksRef.current.push(e.data)
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setVoiceFile(new File([blob], 'recording.webm', { type: 'audio/webm' }))
        stream.getTracks().forEach(t => t.stop())
      }
      mr.start(); mediaRef.current = mr; setRecording(true)
    } catch { toast.error('Нет доступа к микрофону') }
  }
  const stopRecording = () => { mediaRef.current?.stop(); setRecording(false) }

  const allAvatars = [
    ...(avatars ?? []).map(a => ({ ...a, _isTalkingPhoto: false })),
    ...(photos  ?? []).map(p => ({
      avatar_id: p.talking_photo_id, avatar_name: p.talking_photo_name,
      preview_image_url: p.preview_image_url, _isTalkingPhoto: true, _origId: p.talking_photo_id,
    })),
  ]

  const tabs = [
    { id: 'presets' as Tab, label: 'Пресеты',       icon: Sparkles    },
    { id: 'library' as Tab, label: 'Библиотека',    icon: UserSquare2 },
    { id: 'create'  as Tab, label: 'Создать',       icon: Wand2       },
    { id: 'voice'   as Tab, label: 'Голос',         icon: Mic         },
  ]

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Avatar Studio</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Аватары и голоса для HeyGen-видео</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px
              ${tab === t.id ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>
            <t.icon className="h-4 w-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* ── PRESETS ── */}
      {tab === 'presets' && (
        <div className="space-y-8">

          {/* Avatar presets */}
          <div className="space-y-4">
            <div>
              <h2 className="text-base font-semibold">Персонажи-аватары</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Нажми «Создать» — HeyGen сгенерирует аватар по готовому промпту. Появится в Библиотеке через 1-2 минуты.
              </p>
            </div>

            <div className="grid grid-cols-3 gap-4">
              {AVATAR_PRESETS.map(p => (
                <div key={p.id} className="rounded-xl border border-border bg-card p-4 space-y-3 hover:border-primary/40 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-2xl">{p.emoji}</p>
                      <p className="text-sm font-semibold mt-1">{p.name}</p>
                      <p className="text-xs text-muted-foreground">{p.desc}</p>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                        {p.age === 'young' ? '25-35' : p.age === 'middle_aged' ? '35-50' : '55+'}
                      </span>
                      <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                        {p.gender === 'male' ? '♂' : '♀'}
                      </span>
                    </div>
                  </div>

                  <div className="text-[11px] text-muted-foreground bg-muted/40 rounded-lg p-2 leading-relaxed line-clamp-2">
                    {p.voice.desc}
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => createPreset(p)}
                      disabled={creatingPreset === p.id || generateFromPrompt.isPending}
                      className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary py-2 text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      {creatingPreset === p.id
                        ? <><Loader2 className="h-3 w-3 animate-spin" /> Создаю...</>
                        : <><Sparkles className="h-3 w-3" /> Создать</>}
                    </button>
                    <button
                      onClick={() => {
                        setMode('prompt'); setPromptName(p.name)
                        setPrompt(p.prompt); setGender(p.gender); setAge(p.age)
                        setTab('create')
                      }}
                      className="rounded-lg border border-border hover:bg-muted/30 px-2.5 py-2 text-xs text-muted-foreground transition-colors"
                      title="Редактировать промпт"
                    >
                      ✏️
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Voice presets */}
          <div className="space-y-4">
            <div>
              <h2 className="text-base font-semibold">Настройки голоса ElevenLabs</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Скопируй настройки → вставь в поле «Voice settings» при создании канала
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {VOICE_PRESETS.map(vp => (
                <div key={vp.id} className="rounded-xl border border-border bg-card p-4 space-y-3">
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{vp.emoji}</span>
                    <div>
                      <p className="text-sm font-semibold">{vp.name}</p>
                      <p className="text-xs text-muted-foreground">{vp.desc}</p>
                      <p className="text-[11px] text-primary mt-0.5">{vp.recommended_for}</p>
                    </div>
                  </div>

                  {/* Settings preview */}
                  <div className="space-y-1.5">
                    {[
                      { label: 'Stability',         val: vp.settings.stability,        max: 1 },
                      { label: 'Similarity',        val: vp.settings.similarity_boost, max: 1 },
                      { label: 'Style exaggeration', val: vp.settings.style,           max: 1 },
                    ].map(s => (
                      <div key={s.label} className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground w-28 shrink-0">{s.label}</span>
                        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                          <div className="h-full bg-primary rounded-full" style={{ width: `${s.val * 100}%` }} />
                        </div>
                        <span className="text-[10px] text-muted-foreground w-8 text-right">{s.val}</span>
                      </div>
                    ))}
                  </div>

                  <button
                    onClick={() => copyJson(vp.settings, vp.name)}
                    className="w-full flex items-center justify-center gap-1.5 rounded-lg border border-border hover:bg-muted/30 py-2 text-xs text-muted-foreground transition-colors"
                  >
                    <Copy className="h-3 w-3" /> Скопировать настройки
                  </button>
                </div>
              ))}
            </div>
          </div>

        </div>
      )}

      {/* ── LIBRARY ── */}
      {tab === 'library' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{allAvatars.length} аватаров · {voices?.length ?? 0} голосов</p>
            <button onClick={() => { qc.invalidateQueries(); toast.info('Обновляю...') }}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors">
              <RefreshCw className="h-3.5 w-3.5" /> Обновить
            </button>
          </div>
          {(loadA || loadP) ? (
            <div className="flex items-center gap-2 text-muted-foreground text-sm py-8">
              <Loader2 className="h-4 w-4 animate-spin" /> Загружаю из HeyGen...
            </div>
          ) : allAvatars.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <UserSquare2 className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm">Нет аватаров</p>
              <button onClick={() => setTab('presets')} className="text-primary text-sm underline mt-2">
                Создать из пресетов →
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-5 gap-3">
              {allAvatars.map((av: any) => (
                <AvatarCard key={av.avatar_id} avatar={av}
                  onDelete={av._isTalkingPhoto
                    ? () => { if (confirm(`Удалить "${av.avatar_name}"?`)) deleteMutation.mutate(av._origId) }
                    : undefined} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── CREATE ── */}
      {tab === 'create' && (
        <div className="space-y-6 max-w-lg">
          <div className="flex rounded-xl border border-border overflow-hidden">
            {[
              { id: 'upload', label: '📷 Своё фото', sub: 'Загрузи → аватар' },
              { id: 'prompt', label: '✨ По промпту', sub: 'Опиши → AI создаст' },
            ].map(m => (
              <button key={m.id} onClick={() => setMode(m.id as 'upload' | 'prompt')}
                className={`flex-1 py-3 px-4 text-left transition-colors ${mode === m.id ? 'bg-primary/10' : 'hover:bg-muted/30'}`}>
                <p className="text-sm font-medium">{m.label}</p>
                <p className="text-xs text-muted-foreground">{m.sub}</p>
              </button>
            ))}
          </div>

          {mode === 'upload' && (
            <div className="space-y-4">
              {photoPreview ? (
                <div className="relative rounded-xl overflow-hidden">
                  <img src={photoPreview} alt="Preview" className="w-full max-h-64 object-contain bg-muted rounded-xl" />
                  <button onClick={() => { setPhotoFile(null); setPhotoPreview(null) }}
                    className="absolute top-2 right-2 bg-red-950 text-red-400 rounded-lg p-1.5">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <DropZone accept="image/*" label="Перетащи фото или кликни"
                  hint="JPG, PNG, WEBP · лицо чёткое, хорошее освещение" icon={Upload} onFile={handlePhotoSelect} />
              )}
              <input value={photoName} onChange={e => setPhotoName(e.target.value)}
                placeholder="Имя аватара"
                className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              <button onClick={() => createFromPhoto.mutate()}
                disabled={!photoFile || !photoName || createFromPhoto.isPending}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary text-primary-foreground py-3 text-sm font-semibold hover:opacity-90 disabled:opacity-40">
                {createFromPhoto.isPending ? <><Loader2 className="h-4 w-4 animate-spin" /> Создаю...</> : <><Plus className="h-4 w-4" /> Создать</>}
              </button>
            </div>
          )}

          {mode === 'prompt' && (
            <div className="space-y-4">
              <input value={promptName} onChange={e => setPromptName(e.target.value)} placeholder="Имя аватара"
                className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={4}
                placeholder="Опиши внешность на английском: A serious male doctor aged 45, intelligent eyes..."
                className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none" />
              <div className="grid grid-cols-2 gap-3">
                <select value={gender} onChange={e => setGender(e.target.value)}
                  className="rounded-lg border border-border bg-card px-3 py-2.5 text-sm">
                  <option value="male">Мужской</option><option value="female">Женский</option>
                </select>
                <select value={age} onChange={e => setAge(e.target.value)}
                  className="rounded-lg border border-border bg-card px-3 py-2.5 text-sm">
                  <option value="young">Молодой (20–30)</option>
                  <option value="middle_aged">Средний (35–50)</option>
                  <option value="old">Старший (55+)</option>
                </select>
              </div>
              <button onClick={() => generateFromPrompt.mutate({})} disabled={!prompt || generateFromPrompt.isPending}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary text-primary-foreground py-3 text-sm font-semibold hover:opacity-90 disabled:opacity-40">
                {generateFromPrompt.isPending ? <><Loader2 className="h-4 w-4 animate-spin" /> Генерирую...</> : <><Wand2 className="h-4 w-4" /> Сгенерировать</>}
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── VOICE ── */}
      {tab === 'voice' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold flex items-center gap-2"><Mic className="h-4 w-4" /> Клонировать голос</h2>
              <p className="text-xs text-muted-foreground mt-1">30–120 сек чистой речи без фона</p>
            </div>
            <div className="p-5 space-y-4">
              <input value={voiceName} onChange={e => setVoiceName(e.target.value)}
                placeholder="Название голоса" className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              <div className="grid grid-cols-2 gap-3">
                <button onClick={recording ? stopRecording : startRecording}
                  className={`flex flex-col items-center gap-2 rounded-xl border p-4 transition-colors
                    ${recording ? 'border-red-500 bg-red-950/30 text-red-400' : 'border-border hover:border-primary/50 hover:bg-muted/30'}`}>
                  <Mic className={`h-6 w-6 ${recording ? 'animate-pulse' : ''}`} />
                  <span className="text-xs font-medium">{recording ? '⏹ Стоп' : '🎙 Записать'}</span>
                </button>
                <label className="flex flex-col items-center gap-2 rounded-xl border border-border hover:border-primary/50 hover:bg-muted/30 p-4 cursor-pointer transition-colors">
                  <Upload className="h-6 w-6 text-muted-foreground" />
                  <span className="text-xs font-medium">{voiceFile && !recording ? voiceFile.name.slice(0, 18) : '📂 Загрузить аудио'}</span>
                  <input type="file" accept="audio/*" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) setVoiceFile(f) }} />
                </label>
              </div>
              {voiceFile && <div className="flex items-center gap-2 text-xs text-green-400"><CheckCircle2 className="h-4 w-4" /> {voiceFile.name} ({(voiceFile.size/1024).toFixed(0)} KB)</div>}
              <button onClick={() => cloneVoice.mutate()} disabled={!voiceFile || !voiceName || cloneVoice.isPending}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary text-primary-foreground py-3 text-sm font-semibold hover:opacity-90 disabled:opacity-40">
                {cloneVoice.isPending ? <><Loader2 className="h-4 w-4 animate-spin" /> Клонирую...</> : <><Mic className="h-4 w-4" /> Создать голос</>}
              </button>
            </div>
          </div>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold">Голоса HeyGen · {voices?.length ?? 0}</h2>
            </div>
            {loadV
              ? <div className="flex items-center gap-2 p-5 text-muted-foreground text-sm"><Loader2 className="h-4 w-4 animate-spin" /></div>
              : (voices ?? []).map(v => <VoiceCard key={v.voice_id} v={v} />)
            }
          </div>
        </div>
      )}
    </div>
  )
}
