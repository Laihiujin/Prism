"use client";

import { useChatRuntime, AssistantChatTransport } from "@assistant-ui/react-ai-sdk";
import { AssistantRuntimeProvider, ThreadPrimitive, ComposerPrimitive, MessagePrimitive } from "@assistant-ui/react";
import { useState, useEffect, useRef } from "react";
import { nanoid } from "nanoid";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
    Sparkles, Send, User, Bot, Plus, Trash2,
    ChevronDown, ChevronRight, Terminal, Cpu,
    Activity, AlertCircle, MessageSquare
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

// --- Types & Storage ---

interface Thread {
    id: string;
    title: string;
    createdAt: number;
    lastMessageAt: number;
}

const THREADS_STORAGE_KEY = "ai-agent-threads";
const CURRENT_THREAD_KEY = "ai-agent-current-thread";

function getStoredThreads(): Thread[] {
    if (typeof window === "undefined") return [];
    try {
        const stored = localStorage.getItem(THREADS_STORAGE_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch {
        return [];
    }
}

function saveThreads(threads: Thread[]) {
    if (typeof window === "undefined") return;
    localStorage.setItem(THREADS_STORAGE_KEY, JSON.stringify(threads));
}

function getCurrentThreadId(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(CURRENT_THREAD_KEY);
}

function setCurrentThreadId(id: string) {
    if (typeof window === "undefined") return;
    localStorage.setItem(CURRENT_THREAD_KEY, id);
}

// --- Components ---

const MarkdownText = ({ text }: { text: string }) => {
    return (
        <div className="prose prose-invert max-w-none text-sm leading-relaxed">
            <ReactMarkdown>{text}</ReactMarkdown>
        </div>
    );
};

// Thought Process Card Component
const ThoughtProcess = ({ content }: { content: string }) => {
    const [isExpanded, setIsExpanded] = useState(true);

    // Clean up content: remove "> 💭 " prefix if exists
    const cleanContent = content.replace(/^> 💭\s*/, '').trim();

    return (
        <div className="my-2 rounded-lg border border-amber-500/20 bg-amber-500/5 overflow-hidden">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-amber-400/80 hover:bg-amber-500/10 transition-colors"
            >
                {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                <Cpu className="h-3 w-3" />
                <span>思考过程</span>
            </button>
            <AnimatePresence initial={false}>
                {isExpanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                    >
                        <div className="px-3 pb-3 pt-0 text-xs text-amber-200/70 font-mono whitespace-pre-wrap border-t border-amber-500/10">
                            {cleanContent}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

// Tool Execution Component
const ToolExecution = ({ content }: { content: string }) => {
    // Clean up content: remove "> 🔧 " prefix
    const cleanContent = content.replace(/^> 🔧\s*/, '').trim();

    return (
        <div className="my-2 rounded-lg border border-blue-500/20 bg-blue-500/5 overflow-hidden">
            <div className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-blue-400/80 border-b border-blue-500/10">
                <Terminal className="h-3 w-3" />
                <span>工具调用</span>
            </div>
            <div className="px-3 py-2 text-xs text-blue-200/70 font-mono bg-black/20">
                {cleanContent}
            </div>
        </div>
    );
};

// Message Content Parser
const MessageContent = () => {
    return (
        <MessagePrimitive.Content components={{
            Text: ({ text }) => {
                // Check if it's a thought block
                if (text.startsWith("> 💭")) {
                    return <ThoughtProcess content={text} />;
                }
                // Check if it's a tool block
                if (text.startsWith("> 🔧")) {
                    return <ToolExecution content={text} />;
                }
                // Regular markdown
                return <MarkdownText text={text} />;
            }
        }} />
    );
};

// --- Main Component ---

export function AgentChat() {
    const [threads, setThreads] = useState<Thread[]>([]);
    const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
    const [mounted, setMounted] = useState(false);
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);

    // Initialize threads
    useEffect(() => {
        setMounted(true);
        const storedThreads = getStoredThreads();

        if (storedThreads.length === 0) {
            const initialThread: Thread = {
                id: nanoid(),
                title: "新任务",
                createdAt: Date.now(),
                lastMessageAt: Date.now(),
            };
            setThreads([initialThread]);
            setCurrentThreadId(initialThread.id);
            saveThreads([initialThread]);
            setCurrentThreadId(initialThread.id);
        } else {
            setThreads(storedThreads);
            const currentId = getCurrentThreadId();
            if (currentId && storedThreads.some(t => t.id === currentId)) {
                setCurrentThreadId(currentId);
            } else {
                setCurrentThreadId(storedThreads[0].id);
            }
        }
    }, []);

    const runtime = useChatRuntime({
        transport: new AssistantChatTransport({
            api: "/api/chat",
        }),
        onError: (error) => {
            console.error("Chat Error:", error);
        }
    });

    const createNewThread = () => {
        const newThread: Thread = {
            id: nanoid(),
            title: "新任务",
            createdAt: Date.now(),
            lastMessageAt: Date.now(),
        };
        const updatedThreads = [newThread, ...threads];
        setThreads(updatedThreads);
        saveThreads(updatedThreads);
        setCurrentThreadId(newThread.id);
        setCurrentThreadId(newThread.id);
        window.location.reload();
    };

    const deleteThread = (threadId: string) => {
        const updatedThreads = threads.filter(t => t.id !== threadId);
        setThreads(updatedThreads);
        saveThreads(updatedThreads);

        if (currentThreadId === threadId) {
            if (updatedThreads.length > 0) {
                setCurrentThreadId(updatedThreads[0].id);
                setCurrentThreadId(updatedThreads[0].id);
            } else {
                createNewThread();
            }
            window.location.reload();
        }
    };

    const switchThread = (threadId: string) => {
        setCurrentThreadId(threadId);
        setCurrentThreadId(threadId);
        window.location.reload();
    };

    if (!mounted) return null;

    return (
        <AssistantRuntimeProvider runtime={runtime}>
            <div className="flex h-full w-full bg-[#09090b] text-foreground overflow-hidden font-sans">

                {/* Sidebar */}
                <motion.div
                    initial={{ width: 280 }}
                    animate={{ width: isSidebarOpen ? 280 : 0 }}
                    className="border-r border-white/5 bg-black/40 backdrop-blur-xl flex flex-col overflow-hidden relative z-20"
                >
                    <div className="p-4 border-b border-white/5 flex items-center justify-between">
                        <div className="flex items-center gap-2 text-purple-400 font-semibold">
                            <Bot className="h-5 w-5" />
                            <span>OpenManus</span>
                        </div>
                        <Button onClick={createNewThread} size="icon" variant="ghost" className="h-8 w-8 hover:bg-white/10 text-white/70">
                            <Plus className="h-4 w-4" />
                        </Button>
                    </div>

                    <ScrollArea className="flex-1 px-2 py-3">
                        <div className="space-y-1">
                            {threads.map(thread => (
                                <div
                                    key={thread.id}
                                    onClick={() => switchThread(thread.id)}
                                    className={cn(
                                        "group flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-200",
                                        currentThreadId === thread.id
                                            ? "bg-white/10 text-white shadow-sm border border-white/5"
                                            : "text-white/50 hover:bg-white/5 hover:text-white/80"
                                    )}
                                >
                                    <MessageSquare className="h-4 w-4 opacity-70" />
                                    <div className="flex-1 overflow-hidden">
                                        <div className="truncate text-sm font-medium">{thread.title}</div>
                                        <div className="text-[10px] opacity-50 truncate">
                                            {new Date(thread.lastMessageAt).toLocaleTimeString()}
                                        </div>
                                    </div>
                                    <Button
                                        size="icon"
                                        variant="ghost"
                                        className="h-6 w-6 opacity-0 group-hover:opacity-100 hover:bg-red-500/20 hover:text-red-400 transition-all"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            deleteThread(thread.id);
                                        }}
                                    >
                                        <Trash2 className="h-3 w-3" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    </ScrollArea>
                </motion.div>

                {/* Main Chat Area */}
                <div className="flex-1 flex flex-col h-full relative bg-gradient-to-b from-[#0c0c0e] to-[#000000]">

                    {/* Header */}
                    <div className="h-14 border-b border-white/5 bg-black/20 backdrop-blur-md flex items-center justify-between px-6 z-10">
                        <div className="flex items-center gap-3">
                            <Button
                                variant="ghost"
                                size="icon"
                                className="md:hidden text-white/50"
                                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            >
                                <ChevronRight className="h-5 w-5" />
                            </Button>
                            <div>
                                <h2 className="text-sm font-semibold text-white/90">Agent 执行任务</h2>
                                <div className="flex items-center gap-1.5">
                                    <span className="relative flex h-2 w-2">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                                    </span>
                                    <span className="text-[10px] font-medium text-emerald-500/80">SYSTEM ONLINE</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Messages */}
                    <ThreadPrimitive.Root className="flex-1 overflow-hidden flex flex-col">
                        <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto p-4 md:p-6 scroll-smooth">
                            <div className="mx-auto max-w-3xl space-y-6 pb-4">
                                <ThreadPrimitive.Empty>
                                    <motion.div
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="flex flex-col items-center justify-center h-[60vh] text-center space-y-6"
                                    >
                                        <div className="relative">
                                            <div className="absolute -inset-4 bg-purple-500/20 rounded-full blur-xl animate-pulse"></div>
                                            <div className="relative h-20 w-20 rounded-2xl bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center shadow-2xl shadow-purple-500/20">
                                                <Bot className="h-10 w-10 text-white" />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <h3 className="text-2xl font-bold text-white tracking-tight">OpenManus Agent</h3>
                                            <p className="text-white/40 max-w-md text-sm">
                                                全能型 AI 助手，可以执行复杂的网页操作、数据分析和自动化任务。
                                            </p>
                                        </div>
                                        <div className="grid grid-cols-2 gap-3 w-full max-w-md">
                                            {[
                                                "分析最近的视频数据",
                                                "自动发布一条动态",
                                                "检查账号登录状态",
                                                "生成并执行Python脚本"
                                            ].map((suggestion, i) => (
                                                <Button
                                                    key={i}
                                                    variant="outline"
                                                    className="bg-white/5 border-white/10 hover:bg-white/10 text-white/60 hover:text-white text-xs h-auto py-3 justify-start"
                                                >
                                                    <Sparkles className="h-3 w-3 mr-2 text-purple-400" />
                                                    {suggestion}
                                                </Button>
                                            ))}
                                        </div>
                                    </motion.div>
                                </ThreadPrimitive.Empty>

                                <ThreadPrimitive.Messages
                                    components={{
                                        UserMessage: () => (
                                            <motion.div
                                                initial={{ opacity: 0, y: 10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                className="flex gap-4 mb-8 justify-end group"
                                            >
                                                <div className="flex-1 max-w-2xl">
                                                    <div className="bg-gradient-to-br from-indigo-600 to-blue-600 text-white rounded-2xl rounded-tr-sm px-6 py-4 shadow-lg shadow-blue-900/20">
                                                        <MessagePrimitive.Content />
                                                    </div>
                                                </div>
                                                <div className="flex-shrink-0 mt-1">
                                                    <div className="h-9 w-9 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
                                                        <User className="h-5 w-5 text-indigo-400" />
                                                    </div>
                                                </div>
                                            </motion.div>
                                        ),
                                        AssistantMessage: () => (
                                            <motion.div
                                                initial={{ opacity: 0, y: 10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                className="flex gap-4 mb-8"
                                            >
                                                <div className="flex-shrink-0 mt-1">
                                                    <div className="h-9 w-9 rounded-full bg-purple-500/20 border border-purple-500/30 flex items-center justify-center shadow-[0_0_15px_rgba(168,85,247,0.15)]">
                                                        <Bot className="h-5 w-5 text-purple-400" />
                                                    </div>
                                                </div>
                                                <div className="flex-1 max-w-3xl space-y-2">
                                                    <div className="bg-[#1a1a1c] border border-white/5 rounded-2xl rounded-tl-sm px-6 py-5 text-white/90 shadow-xl">
                                                        <MessageContent />
                                                    </div>
                                                </div>
                                            </motion.div>
                                        ),
                                    }}
                                />
                            </div>
                        </ThreadPrimitive.Viewport>

                        {/* Input Area */}
                        <div className="p-4 md:p-6 bg-gradient-to-t from-black via-black to-transparent pt-10">
                            <ComposerPrimitive.Root className="mx-auto max-w-3xl relative">
                                <div className="relative group">
                                    <div className="absolute -inset-0.5 bg-gradient-to-r from-purple-600 to-blue-600 rounded-2xl opacity-20 group-hover:opacity-40 transition duration-500 blur"></div>
                                    <div className="relative flex gap-3 items-end bg-[#121214] border border-white/10 rounded-2xl p-3 shadow-2xl">
                                        <ComposerPrimitive.Input
                                            asChild
                                            autoFocus
                                            placeholder="描述你的任务..."
                                        >
                                            <Textarea
                                                className="flex-1 bg-transparent border-0 text-white placeholder:text-white/30 resize-none focus-visible:ring-0 focus-visible:ring-offset-0 min-h-[50px] max-h-[200px] py-3 px-2 text-base"
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter' && !e.shiftKey) {
                                                        e.preventDefault();
                                                        // Trigger submit manually if needed, but ComposerPrimitive usually handles it
                                                    }
                                                }}
                                            />
                                        </ComposerPrimitive.Input>

                                        <ComposerPrimitive.Send asChild>
                                            <Button
                                                size="icon"
                                                className="h-10 w-10 rounded-xl bg-white text-black hover:bg-white/90 transition-all shadow-lg hover:shadow-white/20 mb-1"
                                            >
                                                <Send className="h-4 w-4" />
                                            </Button>
                                        </ComposerPrimitive.Send>
                                    </div>
                                </div>
                                <div className="text-center mt-3">
                                    <p className="text-[10px] text-white/30 font-medium tracking-wide uppercase">
                                        Powered by OpenManus & Synapse AI
                                    </p>
                                </div>
                            </ComposerPrimitive.Root>
                        </div>
                    </ThreadPrimitive.Root>
                </div>
            </div>
        </AssistantRuntimeProvider>
    );
}
