"use client"

import Link from "next/link"

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-between px-4 py-16 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(99,102,241,0.15),transparent_55%)]" />

      <div className="flex-1 flex flex-col items-center justify-center text-center relative">
        <h1 className="text-[10rem] leading-none font-bold tracking-tighter bg-gradient-to-br from-white via-indigo-200 to-indigo-500 bg-clip-text text-transparent drop-shadow-[0_0_40px_rgba(99,102,241,0.35)]">
          gliss
        </h1>
        <p className="mt-4 text-lg text-gray-400 tracking-wide uppercase">
          Real-time speech coaching
        </p>
      </div>

      <div className="relative grid grid-cols-2 gap-6 w-full max-w-2xl">
        <MenuButton
          href="/practice"
          label="Practice"
          sublabel="Start a session"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-12 h-12">
              <polygon points="6 4 20 12 6 20 6 4" />
            </svg>
          }
        />
        <MenuButton
          href="/sessions"
          label="Past Sessions"
          sublabel="Review your history"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-12 h-12">
              <circle cx="12" cy="12" r="9" />
              <polyline points="12 7 12 12 15 14" />
            </svg>
          }
        />
      </div>
    </main>
  )
}

function MenuButton({
  href,
  label,
  sublabel,
  icon,
}: {
  href: string
  label: string
  sublabel: string
  icon: React.ReactNode
}) {
  return (
    <Link
      href={href}
      className="group relative aspect-square flex flex-col items-center justify-center gap-3 rounded-2xl border border-white/10 bg-gray-900/60 hover:bg-gray-800/80 hover:border-indigo-400/60 active:scale-[0.98] transition-all duration-200 overflow-hidden"
    >
      <span className="pointer-events-none absolute inset-0 bg-gradient-to-br from-indigo-500/0 via-indigo-500/0 to-indigo-500/0 group-hover:from-indigo-500/10 group-hover:to-purple-500/10 transition-colors duration-300" />
      <span className="text-gray-400 group-hover:text-indigo-300 transition-colors">
        {icon}
      </span>
      <span className="text-xl font-semibold tracking-wide text-white">
        {label}
      </span>
      <span className="text-xs uppercase tracking-widest text-gray-500 group-hover:text-gray-400 transition-colors">
        {sublabel}
      </span>
    </Link>
  )
}
