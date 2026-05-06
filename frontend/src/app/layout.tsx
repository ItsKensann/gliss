import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Gliss — Speech Coaching",
  description: "Real-time AI speech coaching for clearer, more confident communication",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} antialiased bg-gray-950 text-white`}>{children}</body>
    </html>
  )
}
