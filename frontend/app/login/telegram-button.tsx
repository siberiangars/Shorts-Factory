'use client'

import { useEffect, useRef } from 'react'
import { signIn } from 'next-auth/react'

interface TelegramUser {
  id: number
  first_name: string
  last_name?: string
  username?: string
  photo_url?: string
  auth_date: number
  hash: string
}

declare global {
  interface Window {
    onTelegramAuth: (user: TelegramUser) => void
  }
}

function clearChildren(el: HTMLElement) {
  while (el.firstChild) el.removeChild(el.firstChild)
}

export function TelegramLoginButton({ botName }: { botName: string }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Глобальный колбэк который вызывает виджет Telegram
    window.onTelegramAuth = async (user: TelegramUser) => {
      await signIn('telegram', {
        id:         String(user.id),
        first_name: user.first_name,
        last_name:  user.last_name  ?? '',
        username:   user.username   ?? '',
        photo_url:  user.photo_url  ?? '',
        auth_date:  String(user.auth_date),
        hash:       user.hash,
        callbackUrl: '/',
        redirect: true,
      })
    }

    const container = containerRef.current
    if (!container) return
    clearChildren(container)

    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.dataset.telegramLogin = botName
    script.dataset.size          = 'large'
    script.dataset.onauth        = 'onTelegramAuth(user)'
    script.dataset.requestAccess = 'write'
    script.dataset.radius        = '8'
    script.async = true
    container.appendChild(script)

    return () => { clearChildren(container) }
  }, [botName])

  return <div ref={containerRef} className="flex justify-center" />
}
