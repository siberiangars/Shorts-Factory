'use client'

import { useState } from 'react'
import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { KeyRound, Loader2, LogOut } from 'lucide-react'

export function ActivateForm({ email, name }: { email: string; name: string }) {
  const [key,     setKey]     = useState('')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [success, setSuccess] = useState(false)
  const { update } = useSession()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!key.trim()) return
    setLoading(true)
    setError('')
    try {
      await api.activateLicense({ key: key.trim(), email, name })
      setSuccess(true)
      // Обновляем JWT-сессию чтобы licenseValid стало true
      await update()
      router.push('/')
      router.refresh()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Неверный ключ. Попробуй ещё раз.')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Автоформатирование: SF-XXXX-XXXX-XXXX
    let val = e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, '')
    setKey(val)
    setError('')
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">Ключ лицензии</label>
        <div className="relative">
          <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={key}
            onChange={handleKeyChange}
            placeholder="SF-XXXX-XXXX-XXXX"
            maxLength={16}
            className="w-full pl-10 pr-4 py-3 rounded-xl border border-border bg-card text-foreground placeholder:text-muted-foreground font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            autoFocus
          />
        </div>
        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}
        {success && (
          <p className="text-sm text-green-400">✓ Лицензия активирована! Перенаправляю...</p>
        )}
      </div>

      <button
        type="submit"
        disabled={loading || !key.trim() || success}
        className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary text-primary-foreground py-3 text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <><Loader2 className="h-4 w-4 animate-spin" /> Проверяю...</>
        ) : (
          'Активировать'
        )}
      </button>

      <button
        type="button"
        onClick={() => signOut({ callbackUrl: '/login' })}
        className="w-full flex items-center justify-center gap-2 rounded-xl border border-border text-muted-foreground py-2.5 text-sm hover:text-red-400 hover:border-red-900 transition-colors"
      >
        <LogOut className="h-4 w-4" /> Войти под другим аккаунтом
      </button>
    </form>
  )
}
