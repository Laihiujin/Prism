"use client"

import * as React from "react"

import type { ToastActionElement, ToastProps } from "@/components/ui/toaster"

const TOAST_LIMIT = 5
const TOAST_REMOVE_DELAY = 1000

type ToasterToast = ToastProps & {
  id: string
  title?: React.ReactNode
  description?: React.ReactNode
  action?: ToastActionElement
}

const actionTypes = {
  ADD_TOAST: "ADD_TOAST",
  UPDATE_TOAST: "UPDATE_TOAST",
  DISMISS_TOAST: "DISMISS_TOAST",
  REMOVE_TOAST: "REMOVE_TOAST",
} as const

type ActionType = typeof actionTypes

type Action =
  | { type: ActionType["ADD_TOAST"]; toast: ToasterToast }
  | { type: ActionType["UPDATE_TOAST"]; toast: Partial<ToasterToast> & Pick<ToasterToast, "id"> }
  | { type: ActionType["DISMISS_TOAST"]; toastId?: ToasterToast["id"] }
  | { type: ActionType["REMOVE_TOAST"]; toastId?: ToasterToast["id"] }

interface State {
  toasts: ToasterToast[]
}

const toastTimeouts = new Map<string, ReturnType<typeof setTimeout>>()

const addToRemoveQueue = (toastId: string) => {
  if (toastTimeouts.has(toastId)) {
    return
  }

  const timeout = setTimeout(() => {
    toastTimeouts.delete(toastId)
    dispatch({
      type: "REMOVE_TOAST",
      toastId,
    })
  }, TOAST_REMOVE_DELAY)

  toastTimeouts.set(toastId, timeout)
}

const reducer = (state: State, action: Action): State => {
  switch (action.type) {
    case actionTypes.ADD_TOAST:
      return {
        ...state,
        toasts: [action.toast, ...state.toasts].slice(0, TOAST_LIMIT),
      }
    case actionTypes.UPDATE_TOAST:
      return {
        ...state,
        toasts: state.toasts.map((toast) =>
          toast.id === action.toast.id ? { ...toast, ...action.toast } : toast
        ),
      }
    case actionTypes.DISMISS_TOAST:
      return {
        ...state,
        toasts: state.toasts.map((toast) =>
          toast.id === action.toastId || action.toastId === undefined ? { ...toast, open: false } : toast
        ),
      }
    case actionTypes.REMOVE_TOAST:
      if (action.toastId === undefined) {
        return { ...state, toasts: [] }
      }
      return {
        ...state,
        toasts: state.toasts.filter((toast) => toast.id !== action.toastId),
      }
    default:
      return state
  }
}

const listeners = new Set<(state: State) => void>()
let memoryState: State = { toasts: [] }

function dispatch(action: Action) {
  memoryState = reducer(memoryState, action)
  listeners.forEach((listener) => listener(memoryState))
}

type Toast = Omit<ToasterToast, "id">

function toast({ ...props }: Toast) {
  const id = Math.random().toString(36).slice(2, 9)

  const duration = props.duration ?? 4000

  const update = (props: ToasterToast) =>
    dispatch({
      type: actionTypes.UPDATE_TOAST,
      toast: { ...props, id },
    })

  const dismiss = (toastId?: string) => {
    dispatch({ type: actionTypes.DISMISS_TOAST, toastId: toastId ?? id })
    addToRemoveQueue(toastId ?? id)
  }

  dispatch({
    type: actionTypes.ADD_TOAST,
    toast: {
      ...props,
      id,
      duration,
      open: true,
      onOpenChange: (open) => {
        if (!open) dismiss(id)
      },
    },
  })

  // Robust auto-dismiss. Radix's built-in close timer is suspended by its
  // pause-on-hover/focus state, and that pause state can get "stuck" (e.g.
  // when a toast is dismissed while the pointer is over it), leaving every
  // later toast stuck on screen forever. Scheduling the dismissal here
  // guarantees each toast closes after `duration` regardless of pointer/focus
  // state. DISMISS on an already-closed toast is a no-op, so this is safe.
  if (duration !== Infinity) {
    setTimeout(() => dismiss(id), duration)
  }

  return {
    id,
    dismiss: () => dismiss(id),
    update,
  }
}

function useToast() {
  const [state, setState] = React.useState<State>(memoryState)

  React.useEffect(() => {
    listeners.add(setState)
    return () => {
      listeners.delete(setState)
    }
  }, [])

  return {
    ...state,
    toast,
    dismiss: (toastId?: string) => {
      dispatch({ type: actionTypes.DISMISS_TOAST, toastId })
      if (toastId) {
        addToRemoveQueue(toastId)
      } else {
        state.toasts.forEach((toastItem) => addToRemoveQueue(toastItem.id))
      }
    },
  }
}

export { toast, useToast }
