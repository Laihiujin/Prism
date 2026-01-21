"use client"

import { EnhancedAIChat } from "@/components/ai-chat/enhanced-chat"

export default function AIAgentPage() {
  return (
    <div className="flex flex-col h-full bg-transparent text-white justify-center items-center p-4 md:p-6">
      <div className="w-full">
        <EnhancedAIChat />
      </div>
    </div>
  )
}
