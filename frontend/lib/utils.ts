import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(iso))
}

export function formatCost(usd: string | null | undefined): string {
  if (!usd) return '—'
  return `$${parseFloat(usd).toFixed(4)}`
}

export function formatDuration(sec: number | null | undefined): string {
  if (!sec) return '—'
  return `${Math.round(sec)}с`
}
