// Shared Framer Motion variants. Durations are short on purpose; MotionConfig in App.jsx
// switches everything to instant transitions when reduced motion is requested.

export const page = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.22, 1, 0.36, 1] } },
  exit: { opacity: 0, y: -6, transition: { duration: 0.15 } },
}

export const stagger = {
  animate: { transition: { staggerChildren: 0.045, delayChildren: 0.04 } },
}

export const item = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.28, ease: [0.22, 1, 0.36, 1] } },
}

export const drawer = {
  initial: { x: '100%' },
  animate: { x: 0, transition: { type: 'spring', stiffness: 380, damping: 38 } },
  exit: { x: '100%', transition: { duration: 0.18 } },
}

export const modal = {
  initial: { opacity: 0, scale: 0.96, y: 8 },
  animate: { opacity: 1, scale: 1, y: 0, transition: { type: 'spring', stiffness: 420, damping: 32 } },
  exit: { opacity: 0, scale: 0.97, transition: { duration: 0.12 } },
}

export const fade = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.2 } },
  exit: { opacity: 0, transition: { duration: 0.15 } },
}

export const collapse = {
  initial: { height: 0, opacity: 0 },
  animate: { height: 'auto', opacity: 1, transition: { duration: 0.22 } },
  exit: { height: 0, opacity: 0, transition: { duration: 0.16 } },
}

export const hoverLift = { whileHover: { y: -2 }, whileTap: { scale: 0.985 } }
