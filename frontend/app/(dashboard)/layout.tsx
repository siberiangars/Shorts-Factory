'use client'

import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { useSession, signOut } from 'next-auth/react'
import { BarChart2, Film, Layers, Radio, UserSquare2, Settings, LogOut } from 'lucide-react'

const nav = [
  { href: '/',          label: 'Дашборд',   icon: BarChart2    },
  { href: '/topics',    label: 'Темы',      icon: Layers       },
  { href: '/videos',    label: 'Видео',     icon: Film         },
  { href: '/channels',  label: 'Каналы',    icon: Radio        },
  { href: '/avatars',   label: 'Аватары',   icon: UserSquare2  },
  { href: '/settings',  label: 'Настройки', icon: Settings     },
]

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { data: session } = useSession()

  const user = session?.user
  const initials = user?.name
    ? user.name.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase()
    : '??'

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <aside className="w-56 shrink-0 border-r border-border flex flex-col bg-background">

        {/* Лого */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-border">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
            style={{ background: 'hsl(43 100% 70%)', color: '#0a0a0b' }}>SF</div>
          <span className="text-xs font-bold tracking-wider text-foreground uppercase">Shorts Factory</span>
        </div>

        {/* Навигация */}
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = pathname === href
            return (
              <Link key={href} href={href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 ${
                  active
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                }`}>
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </Link>
            )
          })}
        </nav>

        {/* Пользователь + выход */}
        <div className="p-3 border-t border-border space-y-2">
          {user && (
            <div className="flex items-center gap-2 px-1">
              {user.image ? (
                <Image
                  src={user.image}
                  alt={user.name ?? ''}
                  width={28} height={28}
                  className="rounded-full shrink-0"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-primary/20 text-primary flex items-center justify-center text-[10px] font-bold shrink-0">
                  {initials}
                </div>
              )}
              <span className="text-xs text-foreground truncate flex-1" title={user.name ?? ''}>
                {user.name}
              </span>
            </div>
          )}
          <button
            onClick={() => signOut({ callbackUrl: '/login' })}
            className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted-foreground hover:text-red-400 hover:bg-red-950/40 transition-colors"
          >
            <LogOut className="h-3.5 w-3.5 shrink-0" />
            Выйти
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="p-8">{children}</div>
      </main>
    </div>
  )
}
