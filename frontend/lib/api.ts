import axios from 'axios'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? ''

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    'Content-Type': 'application/json',
  },
})

// ── Types ─────────────────────────────────────────────────────────────────────

export type VideoStatus =
  | 'pending' | 'generating_script' | 'generating_voice' | 'fetching_broll'
  | 'transcribing' | 'assembling' | 'uploading' | 'done' | 'failed'

export const VIDEO_STATUS_RU: Record<VideoStatus, string> = {
  pending:           'В очереди',
  generating_script: '✍️ Пишу скрипт...',
  generating_voice:  '🎙️ Озвучка...',
  fetching_broll:    '🎬 Скачиваю клипы...',
  transcribing:      '💬 Транскрибирую...',
  assembling:        '🎞️ Монтирую...',
  uploading:         '📤 Загружаю...',
  done:              '✅ Готово',
  failed:            '❌ Ошибка',
}

export const TOPIC_STATUS_RU: Record<string, string> = {
  pending:     'В очереди',
  in_progress: 'Генерируется',
  done:        'Готово',
  failed:      'Ошибка',
  skipped:     'Пропущено',
}

export type TopicStatus = 'pending' | 'in_progress' | 'done' | 'failed' | 'skipped'

export interface Channel {
  id: number
  name: string
  niche: string
  language: string
  voice_id: string
  voice_settings_json: Record<string, unknown>
  google_cloud_project_id: string | null
  youtube_channel_id: string | null
  default_tags: string[]
  description_template: string | null
  script_prompt_template: string | null
  auto_publish_public: boolean
  daily_upload_count: number
  daily_upload_count_reset_at: string | null
  token_expires_at: string | null
  has_oauth: boolean
  created_at: string
  updated_at: string
}

export interface Topic {
  id: number
  channel_id: number
  title: string
  brief: string | null
  status: TopicStatus
  priority: number
  scheduled_at: string | null
  started_at: string | null
  finished_at: string | null
  retry_count: number
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface Video {
  id: number
  topic_id: number
  channel_id: number
  topic_title: string | null
  script_title: string | null
  script_tags: string[]
  script_description: string | null
  broll_keywords: string[]
  duration_sec: number | null
  youtube_video_id: string | null
  youtube_url: string | null
  status: VideoStatus
  generation_cost_usd: string | null
  error_message: string | null
  published_at: string | null
  created_at: string
  updated_at: string
}

export interface VideoDetail extends Video {
  script_text: string | null
  voice_audio_path: string | null
  final_video_path: string | null
  broll_video_hashes: string[]
}

export interface GenerationLog {
  id: number
  video_id: number
  step_name: string
  status: 'start' | 'success' | 'failed'
  duration_ms: number | null
  cost_usd: string | null
  payload_json: Record<string, unknown> | null
  created_at: string
}

export interface HeyGenAvatar {
  avatar_id:    string
  avatar_name:  string
  gender:       string | null
  preview_image_url: string | null
  preview_video_url: string | null
  type?:        string
}

export interface HeyGenVoice {
  voice_id:     string
  name:         string
  language:     string | null
  gender:       string | null
  preview_audio: string | null
}

export interface TalkingPhoto {
  talking_photo_id:   string
  talking_photo_name: string
  preview_image_url:  string | null
  type?:              string
}

export interface License {
  id:                  number
  key:                 string
  note:                string | null
  activated_by_email:  string | null
  activated_by_name:   string | null
  is_active:           boolean
  is_valid:            boolean
  expires_at:          string | null
  created_at:          string
  activated_at:        string | null
}

export interface Stats {
  pending: number
  in_progress: number
  done_today: number
  done_total: number
  avg_cost_usd: string | null
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
  // Stats
  getStats: () => apiClient.get<Stats>('/api/stats').then(r => r.data),

  // Channels
  getChannels: () => apiClient.get<Channel[]>('/api/channels').then(r => r.data),
  getChannel: (id: number) => apiClient.get<Channel>(`/api/channels/${id}`).then(r => r.data),
  createChannel: (data: Partial<Channel>) =>
    apiClient.post<Channel>('/api/channels', data).then(r => r.data),
  updateChannel: (id: number, data: Partial<Channel>) =>
    apiClient.patch<Channel>(`/api/channels/${id}`, data).then(r => r.data),
  deleteChannel: (id: number) => apiClient.delete(`/api/channels/${id}`),
  getAuthUrl: (id: number) =>
    apiClient.get<{ auth_url: string }>(`/api/channels/${id}/auth-url`).then(r => r.data),
  generateTopics: (id: number) =>
    apiClient.post<Topic[]>(`/api/channels/${id}/generate-topics`).then(r => r.data),

  // Topics
  getTopics: (params?: { channel_id?: number; status?: TopicStatus; limit?: number; offset?: number }) =>
    apiClient.get<Topic[]>('/api/topics', { params }).then(r => r.data),
  getTopic: (id: number) => apiClient.get<Topic>(`/api/topics/${id}`).then(r => r.data),
  createTopic: (data: Partial<Topic>) =>
    apiClient.post<Topic[]>('/api/topics', data).then(r => r.data),
  createTopics: (topics: Partial<Topic>[]) =>
    apiClient.post<Topic[]>('/api/topics', { topics }).then(r => r.data),
  updateTopic: (id: number, data: Partial<Topic>) =>
    apiClient.patch<Topic>(`/api/topics/${id}`, data).then(r => r.data),
  deleteTopic: (id: number) => apiClient.delete(`/api/topics/${id}`),
  runTopic: (id: number) => apiClient.post<Topic>(`/api/topics/${id}/run`).then(r => r.data),

  // Videos
  getVideos: (params?: { channel_id?: number; status?: VideoStatus; limit?: number; offset?: number }) =>
    apiClient.get<Video[]>('/api/videos', { params }).then(r => r.data),
  getVideo: (id: number) => apiClient.get<VideoDetail>(`/api/videos/${id}`).then(r => r.data),
  getVideoLogs: (id: number) =>
    apiClient.get<GenerationLog[]>(`/api/videos/${id}/logs`).then(r => r.data),
  publishVideo: (id: number) =>
    apiClient.post<Video>(`/api/videos/${id}/publish`).then(r => r.data),
  retryVideo: (id: number) =>
    apiClient.post<Video>(`/api/videos/${id}/retry`).then(r => r.data),
  deleteVideo: (id: number) =>
    apiClient.delete(`/api/videos/${id}`),
  getPreviewUrl: (id: number) => `${BASE_URL}/api/videos/${id}/preview`,

  // HeyGen Avatar Studio
  getHeyGenAvatars: () =>
    apiClient.get<HeyGenAvatar[]>('/api/heygen/avatars').then(r => r.data),
  getHeyGenVoices: () =>
    apiClient.get<HeyGenVoice[]>('/api/heygen/voices').then(r => r.data),
  getTalkingPhotos: () =>
    apiClient.get<TalkingPhoto[]>('/api/heygen/talking-photos').then(r => r.data),
  uploadAsset: (file: File) => {
    const fd = new FormData(); fd.append('file', file)
    return apiClient.post<{ asset_id: string; image_key: string; url: string }>(
      '/api/heygen/upload-asset', fd, { headers: { 'Content-Type': 'multipart/form-data' } }
    ).then(r => r.data)
  },
  createTalkingPhoto: (data: { name: string; image_key: string }) =>
    apiClient.post('/api/heygen/talking-photo', data).then(r => r.data),
  deleteTalkingPhoto: (id: string) =>
    apiClient.delete(`/api/heygen/talking-photo/${id}`),
  generateAiAvatar: (data: {
    name: string; prompt: string
    gender?: string; age?: string; ethnicity?: string
    orientation?: string; style?: string; pose?: string; appearance?: string
  }) => apiClient.post('/api/heygen/generate-avatar', data).then(r => r.data),
  cloneVoice: (name: string, file: File) => {
    const fd = new FormData(); fd.append('name', name); fd.append('file', file)
    return apiClient.post('/api/heygen/voice-clone', fd,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    ).then(r => r.data)
  },

  // Licenses
  getLicenses: () =>
    apiClient.get<License[]>('/api/licenses').then(r => r.data),
  createLicense: (data: { note?: string; expires_at?: string }) =>
    apiClient.post<License>('/api/licenses', data).then(r => r.data),
  revokeLicense: (id: number) =>
    apiClient.delete(`/api/licenses/${id}`),
  activateLicense: (data: { key: string; email: string; name?: string }) =>
    apiClient.post('/api/licenses/activate', data).then(r => r.data),
}
