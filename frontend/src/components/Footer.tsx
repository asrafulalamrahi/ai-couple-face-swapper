import { Heart } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="w-full border-t border-[rgba(99,102,241,0.08)] mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col sm:flex-row items-center justify-between gap-3">
        <p className="text-xs text-[var(--color-ghost)] flex items-center gap-1.5">
          Built with
          <Heart className="w-3 h-3 text-[var(--color-plasma-start)] fill-[var(--color-plasma-start)]" />
          by Antigravity AI Core
        </p>
        <p className="text-xs text-[var(--color-ghost)] opacity-60">
          InsightFace • OpenCV • Gemini Pro Vision • FastAPI
        </p>
      </div>
    </footer>
  )
}
