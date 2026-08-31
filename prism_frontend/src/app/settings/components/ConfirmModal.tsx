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
      <AlertDialogContent className="border border-border/70 bg-card">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-foreground">{title}</AlertDialogTitle>
          <AlertDialogDescription className="text-foreground/70">{description}</AlertDialogDescription>
        </AlertDialogHeader>

        {requireInput && (
          <div className="space-y-2 py-4">
            <Label htmlFor="confirm-input" className="text-foreground/90">
              请输入 <span className="font-mono font-bold text-destructive">{confirmText}</span> 以确认
            </Label>
            <Input
              id="confirm-input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={`输入 ${confirmText}`}
              className="border-border/80 bg-black text-foreground"
              autoComplete="off"
            />
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel onClick={handleCancel} className="border-border/80 text-foreground hover:bg-accent/50">
            取消
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={!canConfirm}
            className={
              variant === "danger"
                ? "bg-destructive text-foreground hover:bg-destructive/90"
                : "bg-primary text-primary-foreground hover:bg-primary/90"
            }
          >
            确认
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
