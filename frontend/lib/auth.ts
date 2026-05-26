import { NextAuthOptions } from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'
import CredentialsProvider from 'next-auth/providers/credentials'
import crypto from 'crypto'

const ALLOWED_EMAILS       = (process.env.ALLOWED_EMAILS       || '').split(',').map(s => s.trim()).filter(Boolean)
const ALLOWED_TELEGRAM_IDS = (process.env.ALLOWED_TELEGRAM_IDS || '').split(',').map(s => s.trim()).filter(Boolean)
const BOT_TOKEN            = process.env.TELEGRAM_BOT_TOKEN || ''

// Внутренний URL бэкенда (внутри Docker-сети) или публичный как fallback
const INTERNAL_API = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_TOKEN    = process.env.API_AUTH_TOKEN || ''

function verifyTelegramData(data: Record<string, string>): boolean {
  const { hash, ...rest } = data
  if (!hash || !BOT_TOKEN) return false
  const authDate = parseInt(rest.auth_date || '0')
  if (Date.now() / 1000 - authDate > 86400) return false
  const dataCheckString = Object.keys(rest).sort().map(k => `${k}=${rest[k]}`).join('\n')
  const secretKey = crypto.createHash('sha256').update(BOT_TOKEN).digest()
  const expected  = crypto.createHmac('sha256', secretKey).update(dataCheckString).digest('hex')
  return expected === hash
}

async function checkLicense(email: string): Promise<boolean> {
  // Admin email всегда имеет доступ
  if (ALLOWED_EMAILS.includes(email)) return true
  // Остальные — проверяем через API
  try {
    const url = `${INTERNAL_API}/api/licenses/verify?email=${encodeURIComponent(email)}`
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${API_TOKEN}` },
      cache: 'no-store',
    })
    if (!res.ok) return false
    const data = await res.json()
    return data.valid === true
  } catch {
    return false
  }
}

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId:     process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),

    CredentialsProvider({
      id: 'telegram', name: 'Telegram',
      credentials: {
        id:         { label: 'ID',         type: 'text' },
        first_name: { label: 'First Name', type: 'text' },
        last_name:  { label: 'Last Name',  type: 'text' },
        username:   { label: 'Username',   type: 'text' },
        photo_url:  { label: 'Photo URL',  type: 'text' },
        auth_date:  { label: 'Auth Date',  type: 'text' },
        hash:       { label: 'Hash',       type: 'text' },
      },
      async authorize(credentials) {
        if (!credentials) return null
        const { id, first_name, last_name, username, photo_url, auth_date, hash } = credentials
        const payload: Record<string, string> = { id, auth_date, hash }
        if (first_name) payload.first_name = first_name
        if (last_name)  payload.last_name  = last_name
        if (username)   payload.username   = username
        if (photo_url)  payload.photo_url  = photo_url
        if (!verifyTelegramData(payload)) return null
        if (ALLOWED_TELEGRAM_IDS.length > 0 && !ALLOWED_TELEGRAM_IDS.includes(id)) return null
        return {
          id:    `tg_${id}`,
          name:  [first_name, last_name].filter(Boolean).join(' '),
          image: photo_url || null,
          email: username ? `${username}@telegram` : `${id}@telegram`,
        }
      },
    }),
  ],

  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider === 'google') {
        // Если список ALLOWED_EMAILS задан — сначала проверяем его
        // (admin emails всегда пропускаем, остальных пустит только если нет ограничений)
        // Мы НЕ блокируем здесь — блокировка через licenseValid в JWT
      }
      return true
    },

    async jwt({ token, user, account, trigger }) {
      // При первом входе — запоминаем email и проверяем лицензию
      if (account && user) {
        token.userEmail = user.email || ''
        token.userName  = user.name  || ''
        token.userImage = user.image || ''
        token.licenseValid = await checkLicense(user.email || '')
      }
      // При обновлении сессии (после активации ключа) — перепроверяем
      if (trigger === 'update') {
        token.licenseValid = await checkLicense(token.userEmail as string || '')
      }
      return token
    },

    async session({ session, token }) {
      if (session.user) {
        (session.user as any).id           = token.sub
        ;(session.user as any).licenseValid = token.licenseValid
        ;(session.user as any).email        = token.userEmail
      }
      return session
    },
  },

  pages:   { signIn: '/login', error: '/login' },
  session: { strategy: 'jwt' },
  secret:  process.env.NEXTAUTH_SECRET,
}
