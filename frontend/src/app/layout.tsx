import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'NZ Market Aggregator',
  description: 'Automated NZ second-hand and retail market monitor',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        {children}
      </body>
    </html>
  )
}
