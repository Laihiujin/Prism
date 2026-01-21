"use client"

import { useState } from "react"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface ConfirmModalProps {
  open: boolean
  title: string
  description: string
  confirmText?: string
  requireInput?: boolean
  variant?: "default" | "danger"
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmModal({
  open,
  title,
  description,
  confirmText = "",
  requireInput = false,
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const [inputValue, setInputValue] = useState("")
  const canConfirm = !requireInput || inputValue === confirmText

  const handleConfirm = () => {
    if (canConfirm) {
      onConfirm()
      setInputValue("")
    }
  }

  const handleCancel = () => {
    onCancel()
    setInputValue("")
  }

  return (
    <AlertDialog open={open} onOpenChange={(isOpen) => !isOpen && handleCancel()}>
      <AlertDialogContent className="bg-black/95 border border-white/10">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-white">{title}</AlertDialogTitle>
          <AlertDialogDescription className="text-white/70">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>

        {requireInput && (
          <div className="space-y-2 py-4">
            <Label htmlFor="confirm-input" className="text-white/90">
              请输入 <span className="font-mono font-bold text-destructive">{confirmText}</span> 以确认
            </Label>
            <Input
              id="confirm-input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={`输入 ${confirmText}`}
              className="bg-white/5 border-white/20 text-white"
              autoComplete="off"
            />
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel onClick={handleCancel} className="border-white/20 text-white hover:bg-white/10">
            取消
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={!canConfirm}
            className={
              variant === "danger"
                ? "bg-destructive text-white hover:bg-destructive/90"
                : "bg-primary text-black hover:bg-primary/90"
            }
          >
            确认
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
