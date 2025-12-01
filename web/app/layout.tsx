import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import StorageCleaner from '@/components/StorageCleaner'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Crypto Attention Lab',
  description: 'Professional cryptocurrency attention analysis dashboard',
}


export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <StorageCleaner />
        {children}
      </body>
    </html>
  )
}
