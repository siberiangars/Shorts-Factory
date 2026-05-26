'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'next/navigation'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { formatDate, formatCost } from '@/lib/utils'
import { ArrowLeft, ExternalLink, RefreshCw, Globe, Instagram } from 'lucide-react'
import Link from 'next/link'

const LOG_COLORS: Record<string, string> = {
  start:   'text-blue-400',
  success: 'text-green-400',
  failed:  'text-red-400',
}

export default function VideoDetailPage() {
  const { id } = useParams<{ id: string }>()
  const videoId = Number(id)
  const qc = useQueryClient()

  const { data: video } = useQuery({
    queryKey: ['video', videoId],
    queryFn: () => api.getVideo(videoId),
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s !== 'done' && s !== 'failed' ? 5000 : false
    },
  })
  const { data: logs } = useQuery({
    queryKey: ['video-logs', videoId],
    queryFn: () => api.getVideoLogs(videoId),
    refetchInterval: 5000,
  })

  const publishMutation = useMutation({
    mutationFn: () => api.publishVideo(videoId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['video', videoId] }); toast.success('Опубликовано') },
    onError: (e: any) => toast.error(`Ошибка: ${e.response?.data?.detail ?? e.message}`),
  })
  const retryMutation = useMutation({
    mutationFn: () => api.retryVideo(videoId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['video', videoId] }); toast.success('Повтор запущен') },
    onError: () => toast.error('Ошибка'),
  })
  const instagramMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/instagram/${video!.channel_id}/publish/${videoId}`,
        { method: 'POST', headers: { Authorization: `Bearer ${process.env.NEXT_PUBLIC_API_TOKEN ?? ''}` } }
      )
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail) }
      return res.json()
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['video', videoId] }); toast.success('Instagram!') },
    onError: (e: any) => toast.error(`Instagram: ${e.message}`),
  })

  if (!video) return (
    <div className="flex items-center justify-center h-32">
      <p className="font-mono-label text-muted-foreground">Загрузка...</p>
    </div>
  )

  const statusColor = video.status === 'done'
    ? 'bg-green-950 text-green-400'
    : video.status === 'failed'
    ? 'bg-red-950 text-red-400'
    : 'bg-blue-950 text-blue-300'

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/videos" className="rounded-lg border border-border p-2 hover:bg-accent transition-colors">
          <ArrowLeft className="h-4 w-4 text-muted-foreground" />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="section-label" style={{marginBottom:'4px'}}>Видео #{video.id}</div>
          <h1 className="font-display text-2xl font-bold truncate">{video.script_title ?? `Видео #${video.id}`}</h1>
        </div>
        <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${statusColor}`}>{video.status}</span>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Player + actions */}
        <div className="space-y-4">
          {(video.status === 'done' || video.final_video_path) ? (
            <div className="aspect-[9/16] max-h-[65vh] overflow-hidden rounded-xl bg-secondary border border-border">
              <video className="h-full w-full" src={api.getPreviewUrl(videoId)} controls preload="metadata" />
            </div>
          ) : (
            <div className="flex aspect-[9/16] max-h-64 items-center justify-center rounded-xl border border-border bg-card">
              <p className="font-mono-label text-muted-foreground">Видео ещё не готово</p>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {video.youtube_url && (
              <a href={video.youtube_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-pill border border-border bg-secondary px-4 py-2 text-sm text-foreground hover:bg-accent transition-colors">
                <ExternalLink className="h-4 w-4" /> YouTube
              </a>
            )}
            {video.youtube_video_id && !(video as any).published_at && (
              <button onClick={() => publishMutation.mutate()} disabled={publishMutation.isPending}
                className="flex items-center gap-2 rounded-pill bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50">
                <Globe className="h-4 w-4" /> Опубликовать
              </button>
            )}
            {video.status === 'failed' && (
              <button onClick={() => retryMutation.mutate()} disabled={retryMutation.isPending}
                className="flex items-center gap-2 rounded-pill border border-border bg-secondary px-4 py-2 text-sm text-foreground hover:bg-accent disabled:opacity-50">
                <RefreshCw className="h-4 w-4" /> Повторить
              </button>
            )}
            {video.status === 'done' && !(video as any).instagram_media_id && (
              <button onClick={() => instagramMutation.mutate()} disabled={instagramMutation.isPending}
                className="flex items-center gap-2 rounded-pill border px-4 py-2 text-sm disabled:opacity-50"
                style={{borderColor:'rgba(236,72,153,0.3)', background:'rgba(236,72,153,0.08)', color:'rgb(249,168,212)'}}>
                <Instagram className="h-4 w-4" /> {instagramMutation.isPending ? 'Публикую...' : 'Instagram'}
              </button>
            )}
          </div>
        </div>

        {/* Metadata, script, logs */}
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-5">
            <div className="font-mono-label text-muted-foreground mb-4">Метаданные</div>
            <div className="grid grid-cols-2 gap-y-3 text-sm">
              {[
                ['Стоимость', formatCost(video.generation_cost_usd)],
                ['Длительность', video.duration_sec ? `${Math.round(video.duration_sec)}с` : '—'],
                ['YouTube ID', video.youtube_video_id ?? '—'],
                ['Создано', formatDate(video.created_at)],
              ].map(([k, v]) => (
                <div key={k} className="contents">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="text-foreground font-mono text-xs break-all">{v}</span>
                </div>
              ))}
            </div>
          </div>

          {video.script_text && (
            <div className="rounded-xl border border-border bg-card p-5">
              <div className="font-mono-label text-muted-foreground mb-3">Скрипт</div>
              <p className="whitespace-pre-wrap text-sm text-muted-foreground leading-relaxed max-h-40 overflow-y-auto">{video.script_text}</p>
            </div>
          )}

          {video.error_message && (
            <div className="rounded-xl border p-4" style={{background:'rgba(239,68,68,0.06)', borderColor:'rgba(239,68,68,0.25)'}}>
              <div className="font-mono-label text-red-400 mb-2">Ошибка</div>
              <p className="text-sm text-red-300 font-mono break-all">{video.error_message}</p>
            </div>
          )}

          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <div className="border-b border-border px-5 py-3">
              <div className="font-mono-label text-muted-foreground">Лог генерации</div>
            </div>
            <div className="max-h-52 overflow-y-auto divide-y divide-border">
              {(logs ?? []).length === 0 && (
                <div className="px-5 py-4 font-mono-label text-muted-foreground">Нет записей</div>
              )}
              {(logs ?? []).map(l => (
                <div key={l.id} className="flex items-center gap-3 px-5 py-2 text-xs hover:bg-accent/20">
                  <span className={`font-mono font-bold shrink-0 ${LOG_COLORS[l.status] ?? ''}`}>{l.status.toUpperCase()}</span>
                  <span className="font-medium text-foreground">{l.step_name}</span>
                  {l.duration_ms && <span className="text-muted-foreground">{l.duration_ms}ms</span>}
                  {l.cost_usd && <span className="text-primary">${parseFloat(l.cost_usd).toFixed(4)}</span>}
                  <span className="ml-auto text-muted-foreground shrink-0 font-mono-label">{new Date(l.created_at).toLocaleTimeString('ru')}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
