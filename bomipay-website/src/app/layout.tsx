import type { Metadata } from 'next'
import './globals.css'
import Providers from './providers'

export const metadata: Metadata = {
  title: 'BomiPay Ops Intelligence',
  description: 'Operational intelligence dashboard for Nigerian payment processing',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full dark">
      <body className="h-full bg-[#0a0e1a] text-[#f9fafb] antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
