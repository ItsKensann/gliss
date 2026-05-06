import { Recorder } from "@/components/session/Recorder"

export default function SessionPage() {
  return (
    <main className="min-h-screen py-12 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold">Practice Session</h1>
          <p className="text-gray-400 mt-1">Speak naturally — you'll get real-time feedback as you go</p>
        </div>
        <Recorder />
      </div>
    </main>
  )
}
