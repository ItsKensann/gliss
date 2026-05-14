"use client"

import Link from "next/link"

type Star = {
  x: number
  y: number
  size: number
  delay: number
  duration: number
  tint?: "white" | "indigo" | "blue"
}

const STARS: Star[] = [
  { x: 5,  y: 8,  size: 1, delay: 0.0, duration: 4 },
  { x: 12, y: 22, size: 2, delay: 1.2, duration: 5 },
  { x: 18, y: 14, size: 1, delay: 2.4, duration: 3.5 },
  { x: 8,  y: 38, size: 1, delay: 3.0, duration: 4.5 },
  { x: 22, y: 32, size: 2, delay: 0.5, duration: 6, tint: "indigo" },
  { x: 30, y: 11, size: 1, delay: 4.1, duration: 4 },
  { x: 35, y: 28, size: 2, delay: 2.0, duration: 5.5 },
  { x: 42, y: 18, size: 1, delay: 1.8, duration: 4 },
  { x: 48, y: 8,  size: 2, delay: 3.5, duration: 5 },
  { x: 55, y: 22, size: 1, delay: 0.7, duration: 4.5 },
  { x: 62, y: 12, size: 1, delay: 2.5, duration: 3.5 },
  { x: 68, y: 28, size: 2, delay: 1.5, duration: 6, tint: "blue" },
  { x: 75, y: 16, size: 1, delay: 4.0, duration: 5 },
  { x: 82, y: 8,  size: 2, delay: 0.3, duration: 4.5 },
  { x: 88, y: 24, size: 1, delay: 3.2, duration: 4 },
  { x: 92, y: 14, size: 1, delay: 1.9, duration: 5.5 },
  { x: 6,  y: 52, size: 1, delay: 2.7, duration: 4 },
  { x: 14, y: 62, size: 2, delay: 0.9, duration: 5 },
  { x: 20, y: 48, size: 1, delay: 4.5, duration: 4.5 },
  { x: 28, y: 58, size: 1, delay: 1.4, duration: 3.5 },
  { x: 36, y: 68, size: 2, delay: 2.2, duration: 6, tint: "indigo" },
  { x: 44, y: 52, size: 1, delay: 3.8, duration: 4 },
  { x: 52, y: 64, size: 1, delay: 0.6, duration: 5 },
  { x: 60, y: 50, size: 2, delay: 2.9, duration: 5.5, tint: "blue" },
  { x: 68, y: 58, size: 1, delay: 1.7, duration: 4 },
  { x: 76, y: 68, size: 2, delay: 4.3, duration: 6 },
  { x: 84, y: 52, size: 1, delay: 0.4, duration: 4.5 },
  { x: 92, y: 64, size: 1, delay: 3.1, duration: 5 },
  { x: 10, y: 78, size: 1, delay: 2.6, duration: 3.5 },
  { x: 18, y: 88, size: 2, delay: 0.8, duration: 5.5 },
  { x: 26, y: 76, size: 1, delay: 4.2, duration: 4 },
  { x: 34, y: 90, size: 1, delay: 1.3, duration: 4.5 },
  { x: 42, y: 82, size: 2, delay: 3.4, duration: 6, tint: "indigo" },
  { x: 50, y: 76, size: 1, delay: 0.2, duration: 4 },
  { x: 58, y: 90, size: 1, delay: 2.8, duration: 5 },
  { x: 66, y: 80, size: 2, delay: 4.7, duration: 5.5 },
  { x: 74, y: 88, size: 1, delay: 1.1, duration: 4 },
  { x: 82, y: 78, size: 1, delay: 3.6, duration: 4.5 },
  { x: 90, y: 86, size: 2, delay: 0.1, duration: 6, tint: "blue" },
  { x: 96, y: 40, size: 1, delay: 2.3, duration: 4 },
  { x: 3,  y: 70, size: 1, delay: 4.4, duration: 5 },
  { x: 25, y: 4,  size: 1, delay: 1.6, duration: 3.5 },
  { x: 45, y: 38, size: 1, delay: 3.3, duration: 4.5 },
  { x: 65, y: 38, size: 2, delay: 0.0, duration: 5, tint: "indigo" },
  { x: 78, y: 38, size: 1, delay: 2.1, duration: 4 },
  { x: 88, y: 70, size: 1, delay: 4.8, duration: 5.5 },
  { x: 38, y: 6,  size: 1, delay: 1.0, duration: 4 },
  { x: 55, y: 4,  size: 1, delay: 3.7, duration: 4.5 },
  { x: 70, y: 4,  size: 2, delay: 0.9, duration: 5 },
  { x: 85, y: 40, size: 1, delay: 2.5, duration: 4 },
]

type Orb = {
  top: string
  left: string
  size: number
  color: string
  duration: number
  delay: number
}

const ORBS: Orb[] = [
  { top: "12%", left: "8%",  size: 96,  color: "radial-gradient(circle, rgba(167,139,250,0.40), transparent 70%)", duration: 22, delay: 0 },
  { top: "8%",  left: "62%", size: 80,  color: "radial-gradient(circle, rgba(129,140,248,0.35), transparent 70%)", duration: 24, delay: 1.5 },
  { top: "30%", left: "78%", size: 112, color: "radial-gradient(circle, rgba(99,102,241,0.35), transparent 70%)",  duration: 26, delay: 2 },
  { top: "50%", left: "5%",  size: 144, color: "radial-gradient(circle, rgba(124,58,237,0.30), transparent 70%)",  duration: 30, delay: 4 },
  { top: "65%", left: "85%", size: 128, color: "radial-gradient(circle, rgba(96,165,250,0.35), transparent 70%)",  duration: 28, delay: 3 },
  { top: "78%", left: "12%", size: 160, color: "radial-gradient(circle, rgba(139,92,246,0.30), transparent 70%)",  duration: 32, delay: 5 },
]

type Cloud = {
  top: string
  left: string
  width: string
  height: string
  tint: string
  duration: number
  delay: number
}

const CLOUDS: Cloud[] = [
  { top: "10%", left: "15%", width: "55vw", height: "35vh", tint: "radial-gradient(ellipse at center, rgba(139,92,246,0.15), transparent 70%)", duration: 60, delay: 0 },
  { top: "30%", left: "80%", width: "50vw", height: "30vh", tint: "radial-gradient(ellipse at center, rgba(167,139,250,0.12), transparent 70%)", duration: 70, delay: 3 },
  { top: "45%", left: "55%", width: "60vw", height: "40vh", tint: "radial-gradient(ellipse at center, rgba(99,102,241,0.13), transparent 70%)", duration: 75, delay: 5 },
  { top: "70%", left: "5%",  width: "65vw", height: "35vh", tint: "radial-gradient(ellipse at center, rgba(96,165,250,0.12), transparent 70%)",  duration: 90, delay: 10 },
]

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-between px-4 py-16 relative overflow-hidden bg-[linear-gradient(to_bottom,#0b0420_0%,#1a0b3d_30%,#1e1b6b_65%,#0a1840_100%)]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(120,80,200,0.18),transparent_60%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(60,90,200,0.18),transparent_60%)]" />

      {CLOUDS.map((c, i) => (
        <div
          key={`cloud-${i}`}
          aria-hidden
          className="pointer-events-none absolute rounded-full blur-3xl animate-[drift_60s_ease-in-out_infinite_alternate]"
          style={{
            top: c.top,
            left: c.left,
            width: c.width,
            height: c.height,
            background: c.tint,
            animationDuration: `${c.duration}s`,
            animationDelay: `${c.delay}s`,
          }}
        />
      ))}

      {STARS.map((s, i) => (
        <span
          key={`star-${i}`}
          aria-hidden
          className={`pointer-events-none absolute rounded-full animate-[twinkle_4s_ease-in-out_infinite] ${
            s.tint === "indigo" ? "bg-indigo-200" : s.tint === "blue" ? "bg-blue-200" : "bg-white"
          }`}
          style={{
            left: `${s.x}%`,
            top: `${s.y}%`,
            width: `${s.size}px`,
            height: `${s.size}px`,
            animationDelay: `${s.delay}s`,
            animationDuration: `${s.duration}s`,
            boxShadow: s.size >= 2 ? "0 0 4px rgba(255,255,255,0.7)" : undefined,
          }}
        />
      ))}

      {ORBS.map((o, i) => (
        <div
          key={`orb-${i}`}
          aria-hidden
          className="pointer-events-none absolute rounded-full blur-2xl animate-[float_24s_ease-in-out_infinite]"
          style={{
            top: o.top,
            left: o.left,
            width: `${o.size}px`,
            height: `${o.size}px`,
            background: o.color,
            animationDuration: `${o.duration}s`,
            animationDelay: `${o.delay}s`,
          }}
        />
      ))}

      {/* mascot placeholder — swap core disc for character art when the mascot ships */}
      <div
        aria-hidden
        className="pointer-events-none absolute top-[18%] left-1/2 -translate-x-1/2 flex items-center justify-center"
      >
        <div className="absolute w-72 h-72 rounded-full bg-[radial-gradient(circle,rgba(220,225,255,0.35),transparent_65%)] blur-2xl animate-[pulse-glow_6s_ease-in-out_infinite]" />
        <div className="absolute w-48 h-48 rounded-full bg-[radial-gradient(circle,rgba(230,230,255,0.6),rgba(180,170,255,0.2))] blur-md" />
        <div className="relative w-36 h-36 rounded-full bg-gradient-to-br from-white via-indigo-100 to-purple-200 shadow-[0_0_60px_rgba(200,180,255,0.5)]" />
      </div>

      <div className="flex-1" />

      <div className="relative z-10 grid grid-cols-2 gap-6 w-full max-w-2xl">
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
    <Link href={href} className="group relative block h-44 sm:h-48">
      <span
        aria-hidden
        className="pointer-events-none absolute -inset-4 bg-gradient-to-br from-indigo-500/30 via-purple-500/30 to-blue-500/30 blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"
      />
      <div className="relative h-full w-full rounded-xl transition-transform duration-300 ease-out group-hover:-translate-y-1 group-hover:scale-[1.02]">
        <span
          aria-hidden
          className="absolute inset-0 rounded-xl bg-[conic-gradient(from_0deg,rgba(165,180,252,0.45),rgba(192,132,252,0.45),rgba(147,197,253,0.45),rgba(165,180,252,0.45))] opacity-70 group-hover:opacity-100 group-hover:animate-[border-spin_8s_linear_infinite] transition-opacity duration-500"
        />
        <div className="absolute inset-[1px] rounded-[11px] bg-gradient-to-br from-indigo-950/80 via-purple-950/60 to-blue-950/80 backdrop-blur-sm flex flex-col items-center justify-center gap-3">
          <span className="text-indigo-300 group-hover:text-white transition-colors duration-300">
            {icon}
          </span>
          <span className="text-xl font-semibold tracking-wide text-white">
            {label}
          </span>
          <span className="text-xs uppercase tracking-widest text-gray-400 group-hover:text-indigo-200 transition-colors">
            {sublabel}
          </span>
        </div>
      </div>
    </Link>
  )
}
