import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import { authOptions } from '@/lib/auth'
import { ActivateForm } from './activate-form'

export default async function ActivatePage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/login')

  const licenseValid = (session.user as any)?.licenseValid
  if (licenseValid) redirect('/')

  const email = (session.user as any)?.email || session.user?.email || ''
  const name  = session.user?.name || ''

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
            <h1 className="text-2xl font-bold tracking-tight">Активация лицензии</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Привет, {name || email}! Введи ключ чтобы получить доступ.
            </p>
          </div>
        </div>

        <ActivateForm email={email} name={name} />

        <p className="text-center text-xs text-muted-foreground">
          Нет ключа? Обратись к администратору.
        </p>
      </div>
    </div>
  )
}
