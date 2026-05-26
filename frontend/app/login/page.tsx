import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import { authOptions } from '@/lib/auth'
import { LoginButtons } from './login-buttons'

export default async function LoginPage() {
  const session = await getServerSession(authOptions)
  if (session) redirect('/')

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-8 px-4">

        <div className="flex flex-col items-center gap-4">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center text-xl font-black"
            style={{ background: 'hsl(43 100% 70%)', color: '#0a0a0b' }}
          >
            SF
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-tight">Shorts Factory</h1>
            <p className="text-sm text-muted-foreground mt-1">Войди чтобы продолжить</p>
          </div>
        </div>

        <LoginButtons telegramBotName={process.env.TELEGRAM_BOT_USERNAME || ''} />

        <p className="text-center text-xs text-muted-foreground">
          Доступ только для авторизованных пользователей
        </p>
      </div>
    </div>
  )
}
