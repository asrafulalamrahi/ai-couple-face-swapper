import { Sparkles } from 'lucide-react'

export default function Header() {
  return (
    <header className="w-full border-b border-[rgba(99,102,241,0.1)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--color-uv-start)] to-[var(--color-uv-end)] flex items-center justify-center shadow-lg shadow-[var(--color-uv-start)]/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1
              className="text-lg font-bold tracking-tight bg-gradient-to-r from-[var(--color-uv-start)] via-[var(--color-uv-mid)] to-[var(--color-cyan-mid)] bg-clip-text text-transparent"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Antigravity AI
            </h1>
            <p className="text-xs text-[var(--color-ghost)] -mt-0.5">
              Couple Face Swap Studio
            </p>
          </div>
        </div>

        {/* Version Badge */}
        <div className="flex items-center gap-3">
          <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full bg-[var(--color-glass-light)] text-[var(--color-uv-glow)] border border-[rgba(99,102,241,0.15)]">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-success)] animate-pulse" />
            v4.0 Production
          </span>
        </div>
      </div>
    </header>
  )
}
