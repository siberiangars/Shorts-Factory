import { withAuth } from 'next-auth/middleware'
import { NextResponse } from 'next/server'

export default withAuth(
  function middleware(req) {
    const token = req.nextauth.token as any
    const { pathname } = req.nextUrl

    // Страница активации — пускаем даже без лицензии (но нужен логин)
    if (pathname.startsWith('/activate')) return NextResponse.next()

    // Если нет лицензии — на страницу активации
    if (token && token.licenseValid === false) {
      return NextResponse.redirect(new URL('/activate', req.url))
    }

    return NextResponse.next()
  },
  {
    pages: { signIn: '/login' },
    callbacks: {
      authorized: ({ token }) => !!token,
    },
  }
)

export const config = {
  matcher: ['/((?!login|activate|api/auth|_next/static|_next/image|favicon.ico).*)'],
}
