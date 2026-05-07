export type PromptCategory = "Interview" | "Storytelling" | "Impromptu" | "Technical"

export interface Prompt {
  id: string
  category: PromptCategory
  text: string
}

export const PROMPTS: Prompt[] = [
  { id: "iv-1", category: "Interview", text: "Tell me about yourself." },
  { id: "iv-2", category: "Interview", text: "Walk me through a project you're proud of and what you contributed." },
  { id: "iv-3", category: "Interview", text: "Describe a time you faced a difficult problem and how you solved it." },
  { id: "iv-4", category: "Interview", text: "What's a weakness you've been actively working on, and how?" },

  { id: "st-1", category: "Storytelling", text: "Share a moment that changed how you think about something." },
  { id: "st-2", category: "Storytelling", text: "Tell the story of the best meal you've ever had." },
  { id: "st-3", category: "Storytelling", text: "Describe a person who shaped who you are today." },
  { id: "st-4", category: "Storytelling", text: "Talk about a small decision that led to a big consequence." },

  { id: "im-1", category: "Impromptu", text: "If you could master any skill instantly, what would it be and why?" },
  { id: "im-2", category: "Impromptu", text: "Argue for or against the statement: 'It's better to be respected than liked.'" },
  { id: "im-3", category: "Impromptu", text: "What's one thing most people get wrong about your hometown?" },
  { id: "im-4", category: "Impromptu", text: "If you had to teach a class on something tomorrow, what would it be?" },

  { id: "tc-1", category: "Technical", text: "Explain a technical concept you understand well to a non-technical friend." },
  { id: "tc-2", category: "Technical", text: "Describe the architecture of an app you've built or worked on." },
  { id: "tc-3", category: "Technical", text: "Walk through how you'd debug a system that's suddenly slow in production." },
]

export const CATEGORIES: PromptCategory[] = ["Interview", "Storytelling", "Impromptu", "Technical"]

export function getPrompt(id: string | null | undefined): Prompt | undefined {
  if (!id) return undefined
  return PROMPTS.find((p) => p.id === id)
}

export function promptsInCategory(category: PromptCategory): Prompt[] {
  return PROMPTS.filter((p) => p.category === category)
}

export function randomPromptInCategory(category: PromptCategory): Prompt {
  const list = promptsInCategory(category)
  return list[Math.floor(Math.random() * list.length)]
}
