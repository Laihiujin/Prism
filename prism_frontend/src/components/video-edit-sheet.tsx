"use client"

import { useState } from "react"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"

interface VideoEditSheetProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    video?: {
        id: string
        title: string
        description?: string
        tags?: string[]
        selectedAccount?: string
    }
    accounts: Array<{
        id: string
        platform: string
        nickname: string
    }>
    onSave: (data: {
        accountId: string
        description: string
        tags: string[]
    }) => void
}

export function VideoEditSheet({
    open,
    onOpenChange,
    video,
    accounts,
    onSave,
}: VideoEditSheetProps) {
    const [selectedAccount, setSelectedAccount] = useState(video?.selectedAccount || "")
    const [description, setDescription] = useState(video?.description || "")
    const [tags, setTags] = useState<string[]>(video?.tags || [])
    const [tagInput, setTagInput] = useState("")

    const handleAddTag = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter" && tagInput.trim()) {
            e.preventDefault()
            const newTag = tagInput.trim()
            if (!tags.includes(newTag)) {
                setTags([...tags, newTag])
            }
            setTagInput("")
        }
    }

    const handleRemoveTag = (tagToRemove: string) => {
        setTags(tags.filter(tag => tag !== tagToRemove))
    }

    const handleSave = () => {
        onSave({
            accountId: selectedAccount,
            description,
            tags,
        })
        onOpenChange(false)
    }

    // Handle @ mentions in description
    const handleDescriptionChange = (value: string) => {
        setDescription(value)

        // Auto-detect @ mentions and suggest tags
        const mentionMatch = value.match(/@(\w+)/g)
        if (mentionMatch) {
            const newTags = mentionMatch.map(m => m.substring(1))
            const uniqueTags = [...new Set([...tags, ...newTags])]
            setTags(uniqueTags)
        }
    }

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent className="w-full sm:max-w-lg bg-black border-white/10">
                <SheetHeader>
                    <SheetTitle>编辑视频</SheetTitle>
                    <SheetDescription>
                        为视频选择账号、添加标签和编辑描述
                    </SheetDescription>
                </SheetHeader>

                <div className="mt-6 space-y-6">
                    {/* Account Selection */}
                    <div className="space-y-2">
                        <Label htmlFor="account">选择账号</Label>
                        <Select value={selectedAccount} onValueChange={setSelectedAccount}>
                            <SelectTrigger id="account" className="rounded-xl">
                                <SelectValue placeholder="选择发布账号" />
                            </SelectTrigger>
                            <SelectContent className="bg-black border-white/10">
                                {accounts.map((account) => (
                                    <SelectItem key={account.id} value={account.id}>
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline" className="text-xs">
                                                {account.platform}
                                            </Badge>
                                            <span>{account.nickname}</span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Tags Input */}
                    <div className="space-y-2">
                        <Label htmlFor="tags">标签</Label>
                        <div className="space-y-2">
                            <Input
                                id="tags"
                                placeholder="输入标签后按回车添加 (支持 @提及)"
                                value={tagInput}
                                onChange={(e) => setTagInput(e.target.value)}
                                onKeyDown={handleAddTag}
                                className="rounded-xl"
                            />
                            <div className="flex flex-wrap gap-2">
                                {tags.map((tag) => (
                                    <Badge
                                        key={tag}
                                        variant="secondary"
                                        className="rounded-full pl-3 pr-1 py-1"
                                    >
                                        <span className="mr-1">#{tag}</span>
                                        <button
                                            onClick={() => handleRemoveTag(tag)}
                                            className="ml-1 hover:bg-white/20 rounded-full p-0.5"
                                        >
                                            <X className="h-3 w-3" />
                                        </button>
                                    </Badge>
                                ))}
                            </div>
                        </div>
                        <p className="text-xs text-white/50">
                            提示: 在描述中使用 @标签名 会自动添加到标签列表
                        </p>
                    </div>

                    {/* Description Editor */}
                    <div className="space-y-2">
                        <Label htmlFor="description">视频描述</Label>
                        <Textarea
                            id="description"
                            placeholder="输入视频描述... 使用 @标签 来添加标签"
                            value={description}
                            onChange={(e) => handleDescriptionChange(e.target.value)}
                            className="min-h-[200px] rounded-xl resize-none"
                        />
                        <div className="flex justify-between text-xs text-white/50">
                            <span>{description.length} 字符</span>
                            <span>支持 @ 提及自动添加标签</span>
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-3 pt-4">
                        <Button
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            className="flex-1 rounded-xl"
                        >
                            取消
                        </Button>
                        <Button
                            onClick={handleSave}
                            disabled={!selectedAccount}
                            className="flex-1 rounded-xl"
                        >
                            保存
                        </Button>
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    )
}
