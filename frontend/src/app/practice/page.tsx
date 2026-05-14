"use client"

import Link from "next/link"

export default function PracticePage() {
  return (
    <main className="min-h-screen px-4 py-10">
      <div className="max-w-2xl mx-auto">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors mb-8"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 0 1-.02 1.06L8.832 10l3.938 3.71a.75.75 0 1 1-1.04 1.08l-4.5-4.25a.75.75 0 0 1 0-1.08l4.5-4.25a.75.75 0 0 1 1.06.02z" clipRule="evenodd" />
          </svg>
          Back
        </Link>

        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">Practice</h1>
          <p className="text-gray-400 mt-2 text-sm">Choose how you want to practice.</p>
        </header>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href="/sandbox"
            className="group relative flex flex-col items-start gap-3 p-6 rounded-2xl border border-white/10 bg-gray-900/60 hover:bg-gray-800/80 hover:border-indigo-400/60 active:scale-[0.98] transition-all duration-200 overflow-hidden min-h-[180px]"
          >
            <span className="pointer-events-none absolute inset-0 bg-gradient-to-br from-indigo-500/0 via-indigo-500/0 to-indigo-500/0 group-hover:from-indigo-500/10 group-hover:to-purple-500/10 transition-colors duration-300" />
            <span className="text-gray-400 group-hover:text-indigo-300 transition-colors">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-9 h-9">
                <line x1="4" y1="6" x2="20" y2="6" />
                <line x1="4" y1="12" x2="20" y2="12" />
                <line x1="4" y1="18" x2="20" y2="18" />
                <circle cx="9" cy="6" r="2" fill="currentColor" />
                <circle cx="15" cy="12" r="2" fill="currentColor" />
                <circle cx="7" cy="18" r="2" fill="currentColor" />
              </svg>
            </span>
            <span className="mt-auto">
              <span className="block text-lg font-semibold tracking-wide text-white">
                Sandbox
              </span>
              <span className="block text-xs uppercase tracking-widest text-gray-500 group-hover:text-gray-400 transition-colors mt-1">
                Single prompt, your own duration
              </span>
            </span>
          </Link>

          <div
            aria-disabled="true"
            className="relative flex flex-col items-start gap-3 p-6 rounded-2xl border border-white/10 bg-gray-900/40 opacity-60 cursor-not-allowed min-h-[180px]"
          >
            <span className="absolute top-4 right-4 px-2 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-400/30 text-indigo-200 text-[10px] font-medium uppercase tracking-wider">
              Coming soon
            </span>
            <span className="text-gray-500">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-9 h-9">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </span>
            <span className="mt-auto">
              <span className="block text-lg font-semibold tracking-wide text-gray-300">
                Interview series
              </span>
              <span className="block text-xs uppercase tracking-widest text-gray-600 mt-1">
                A sequence of prompts
              </span>
            </span>
          </div>
        </div>
      </div>
    </main>
  )
}
