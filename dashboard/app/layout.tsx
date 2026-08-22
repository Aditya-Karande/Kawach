import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Noto_Sans_Devanagari, Yatra_One } from 'next/font/google'
import './globals.css'

const devanagari = Noto_Sans_Devanagari({ subsets: ['devanagari'], weight: ['700', '800', '900'], variable: '--font-devanagari' })
const titleDevanagari = Yatra_One({ subsets: ['devanagari'], weight: '400', variable: '--font-title-devanagari' })

export const metadata: Metadata = {
  title: 'Kawach — Stay close. Stay calm.',
  description: 'A calmer way for parents to stay close to what matters online.',
  generator: 'Kawach',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export const viewport: Viewport = {
  colorScheme: 'light dark',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f5f2e9' },
    { media: '(prefers-color-scheme: dark)', color: '#24352f' },
  ],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`${devanagari.variable} ${titleDevanagari.variable}`}>
      <body className="antialiased">
        {children}
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
