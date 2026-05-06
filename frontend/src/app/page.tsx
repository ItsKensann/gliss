import Link from "next/link"

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="text-center max-w-2xl">
        <h1 className="text-7xl font-bold tracking-tight mb-4 bg-gradient-to-br from-white to-gray-400 bg-clip-text text-transparent">
          gliss
        </h1>
        <p className="text-xl text-gray-400 mb-3">Real-time speech coaching powered by AI</p>
        <p className="text-gray-500 mb-12 max-w-md mx-auto leading-relaxed">
          Get live feedback on filler words, pacing, eye contact, and clarity — as you speak.
        </p>
        <Link
          href="/session"
          className="inline-block bg-indigo-500 hover:bg-indigo-600 active:scale-95 text-white px-8 py-4 rounded-2xl font-semibold text-lg transition-all duration-200"
        >
          Start practicing
        </Link>
      </div>
    </main>
  )
}
