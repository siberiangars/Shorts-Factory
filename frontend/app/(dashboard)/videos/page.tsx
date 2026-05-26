'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { RefreshCw, Globe, Trash2, ExternalLink, Play } from 'lucide-react'
import { api, type Video, VIDEO_STATUS_RU } from '@/lib/api'
import { formatDate, formatCost } from '@/lib/utils'

const STATUS_COLORS: Record<Video['status'], string> = {
  pending:           'bg-zinc-800 text-zinc-400',
  generating_script: 'bg-blue-950 text-blue-300',
  generating_voice:  'bg-indigo-950 text-indigo-300',
  fetching_broll:    'bg-purple-950 text-purple-300',
  transcribing:      'bg-violet-950 text-violet-300',
  assembling:        'bg-amber-950 text-amber-300',
  uploading:         'bg-orange-950 text-orange-300',
  done:              'bg-green-950 text-green-300',
  failed:            'bg-red-950 text-red-400',
}

const STATUS_FILTERS = [
  { value: '', label: 'Все статусы' },
  { value: 'pending', label: 'В очереди' },
  { value: 'generating_script', label: 'Скрипт' },
  { value: 'generating_voice', label: 'Озвучка' },
  { value: 'fetching_broll', label: 'Клипы' },
  { value: 'transcribing', label: 'Транскрипция' },
  { value: 'assembling', label: 'Монтаж' },
  { value: 'uploading', label: 'Загрузка' },
  { value: 'done', label: 'Готово' },
  { value: 'failed', label: 'Ошибка' },
]

function StatusBadge({ status }: { status: Video['status'] }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[status]}`}>
      {VIDEO_STATUS_RU[status]}
    </span>
  )
}

function VideoCard({ v, onRetry, onPublish, onDelete }: {
  v: Video
  onRetry: (id: number) => void
  onPublish: (id: number) => void
  onDelete: (id: number) => void
}) {
  const [hovered, setHovered] = useState(false)
  const title = v.script_title || v.topic_title || `Видео #${v.id}`
  const isActive = !['pending', 'done', 'failed'].includes(v.status)
  const isDone = v.status === 'done'
  const isFailed = v.status === 'failed'

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden flex flex-col group">
      {/* Preview area */}
      <div
        className="relative bg-muted flex-shrink-0 cursor-pointer"
        style={{ aspectRatio: '9/16', maxHeight: '200px' }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {isDone ? (
          <>
            <video
              className="w-full h-full object-cover"
              src={api.getPreviewUrl(v.id)}
              preload="none"
              muted
              loop
              ref={el => { if (el) { hovered ? el.play().catch(()=>{}) : (el.pause(), el.currentTime=0) } }}
            />
            {!hovered && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                <Play className="h-8 w-8 text-white opacity-70" />
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-2 p-3">
            {isActive && <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />}
            <StatusBadge status={v.status} />
            {isActive && <p className="text-xs text-muted-foreground text-center line-clamp-2 mt-1">{title}</p>}
            {isFailed && <p className="text-xs text-red-400 text-center line-clamp-2 px-2">{v.error_message?.slice(0,80)}</p>}
          </div>
        )}

        {/* Top badges */}
        <div className="absolute top-1.5 left-1.5 flex gap-1 flex-wrap">
          {isDone && <StatusBadge status={v.status} />}
          {v.youtube_video_id && (
            <span className="bg-red-600 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">YT</span>
          )}
          {(v as any).instagram_media_id && (
            <span className="bg-pink-600 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">IG</span>
          )}
        </div>

        {/* Active pulse indicator */}
        {isActive && (
          <div className="absolute top-1.5 right-1.5">
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-2.5 flex flex-col gap-1.5 flex-1">
        <p className="text-xs font-semibold leading-tight line-clamp-2">{title}</p>

        {isActive && (
          <p className="text-[11px] text-primary animate-pulse">{VIDEO_STATUS_RU[v.status]}</p>
        )}

        <div className="flex items-center gap-2 text-[11px] text-muted-foreground flex-wrap">
          {v.generation_cost_usd && <span>{formatCost(v.generation_cost_usd)}</span>}
          {v.duration_sec && <span>{Math.round(v.duration_sec)} сек</span>}
          <span className="ml-auto">{formatDate(v.created_at)}</span>
        </div>

        {/* Action buttons */}
        <div className="flex gap-1 mt-0.5">
          {isDone && !v.youtube_video_id && (
            <button
              onClick={() => onPublish(v.id)}
              className="flex-1 flex items-center justify-center gap-1 rounded-md bg-green-900 hover:bg-green-800 text-green-300 text-[11px] py-1 transition-colors"
              title="Опубликовать на YouTube"
            >
              <Globe className="h-3 w-3" /> YouTube
            </button>
          )}
          {v.youtube_video_id && (
            <a
              href={v.youtube_url || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 flex items-center justify-center gap-1 rounded-md bg-red-950 hover:bg-red-900 text-red-400 text-[11px] py-1 transition-colors"
              title="Открыть на YouTube"
            >
              <ExternalLink className="h-3 w-3" /> YouTube
            </a>
          )}
          {isFailed && (
            <button
              onClick={() => onRetry(v.id)}
              className="flex-1 flex items-center justify-center gap-1 rounded-md bg-amber-950 hover:bg-amber-900 text-amber-300 text-[11px] py-1 transition-colors"
              title="Повторить генерацию"
            >
              <RefreshCw className="h-3 w-3" /> Повторить
            </button>
          )}
          <Link
            href={`/videos/${v.id}`}
            className="flex items-center justify-center rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-[11px] px-2 py-1 transition-colors"
            title="Подробнее"
          >
            Детали
          </Link>
          <button
            onClick={() => { if (confirm(`Удалить «${title.slice(0,40)}»?`)) onDelete(v.id) }}
            className="flex items-center justify-center rounded-md bg-zinc-800 hover:bg-red-950 text-zinc-500 hover:text-red-400 px-2 py-1 transition-colors"
            title="Удалить"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  )
}

export default function VideosPage() {
  const [filterStatus, setFilterStatus] = useState<Video['status'] | ''>('')
  const qc = useQueryClient()

  const { data: videos, isLoading } = useQuery({
    queryKey: ['videos', filterStatus],
    queryFn: () => api.getVideos({ ...(filterStatus ? { status: filterStatus as Video['status'] } : {}), limit: 60 }),
    refetchInterval: (query) => {
      const vids = query.state.data
      if (!vids) return 5000
      return vids.some(v => !['done', 'failed', 'pending'].includes(v.status)) ? 3000 : 10000
    },
  })

  const retryMutation = useMutation({
    mutationFn: (id: number) => api.retryVideo(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['videos'] }); toast.success('Повтор запущен') },
    onError: () => toast.error('Ошибка повтора'),
  })

  const publishMutation = useMutation({
    mutationFn: (id: number) => api.publishVideo(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['videos'] }); toast.success('Опубликовано!') },
    onError: (e: any) => toast.error(`Ошибка: ${e.response?.data?.detail ?? e.message}`),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteVideo(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['videos'] })
      qc.invalidateQueries({ queryKey: ['topics'] })
      toast.success('Удалено')
    },
    onError: () => toast.error('Ошибка удаления'),
  })

  const done = videos?.filter(v => v.status === 'done').length ?? 0
  const failed = videos?.filter(v => v.status === 'failed').length ?? 0
  const active = videos?.filter(v => !['done','failed','pending'].includes(v.status)).length ?? 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Видео</h1>
          {videos && (
            <p className="text-sm text-muted-foreground mt-0.5">
              Всего: {videos.length}
              {done > 0 && <span className="text-green-500"> · Готово: {done}</span>}
              {active > 0 && <span className="text-blue-400"> · Генерируется: {active}</span>}
              {failed > 0 && <span className="text-red-400"> · Ошибок: {failed}</span>}
            </p>
          )}
        </div>
        <select
          className="rounded-md border bg-background px-3 py-2 text-sm"
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value as Video['status'] | '')}
        >
          {STATUS_FILTERS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
        </select>
      </div>

      {isLoading && <p className="text-muted-foreground text-sm">Загрузка...</p>}

      {!isLoading && videos?.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <p className="text-lg">Видео нет</p>
          <p className="text-sm mt-1">Запусти тему на странице <a href="/topics" className="text-primary underline">Темы</a></p>
        </div>
      )}

      <div className="grid grid-cols-5 gap-3">
        {(videos ?? []).map(v => (
          <VideoCard
            key={v.id}
            v={v}
            onRetry={retryMutation.mutate}
            onPublish={publishMutation.mutate}
            onDelete={deleteMutation.mutate}
          />
        ))}
      </div>
    </div>
  )
}
