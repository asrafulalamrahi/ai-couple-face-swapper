export default function ProcessingOverlay({ progress }: { progress: number }) {
  const clampedProgress = Math.min(100, Math.max(0, progress))

  const steps = [
    { label: 'Uploading images', threshold: 10 },
    { label: 'Detecting faces with InsightFace', threshold: 25 },
    { label: 'Mapping husband → male target', threshold: 40 },
    { label: 'Mapping wife → female target', threshold: 55 },
    { label: 'Applying skin tone harmonization', threshold: 70 },
    { label: 'Body proportion calibration', threshold: 80 },
    { label: 'Lighting harmonization', threshold: 90 },
    { label: 'Rendering final output', threshold: 95 },
  ]

  const currentStep = steps.filter((s) => clampedProgress >= s.threshold).length

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="glass-card p-10 max-w-lg w-full text-center animate-fade-in-up animate-pulse-glow">
        {/* Spinner */}
        <div className="flex justify-center mb-8">
          <div className="relative">
            <div className="spinner" />
            <div
              className="absolute inset-0 rounded-full"
              style={{
                background: 'radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)',
                animation: 'pulseGlow 2s ease-in-out infinite',
              }}
            />
          </div>
        </div>

        {/* Title */}
        <h2
          className="text-2xl font-bold mb-2 bg-gradient-to-r from-[var(--color-uv-start)] via-[var(--color-uv-mid)] to-[var(--color-cyan-mid)] bg-clip-text text-transparent"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          Processing...
        </h2>
        <p className="text-sm text-[var(--color-ghost)] mb-6">
          Antigravity AI is executing the face swap pipeline
        </p>

        {/* Progress Bar */}
        <div className="mb-6">
          <div className="flex justify-between text-xs text-[var(--color-ghost)] mb-2">
            <span>Progress</span>
            <span>{Math.round(clampedProgress)}%</span>
          </div>
          <div className="progress-bar-track">
            <div
              className="progress-bar-fill"
              style={{ width: `${clampedProgress}%` }}
            />
          </div>
        </div>

        {/* Steps */}
        <div className="text-left space-y-2">
          {steps.map((step, i) => {
            const isActive = i < currentStep
            const isCurrent = i === currentStep
            return (
              <div
                key={i}
                className={`flex items-center gap-3 text-sm transition-all duration-300 ${
                  isActive
                    ? 'text-[var(--color-success)]'
                    : isCurrent
                    ? 'text-[var(--color-uv-glow)]'
                    : 'text-[var(--color-ghost)] opacity-40'
                }`}
              >
                <span className="w-5 text-center">
                  {isActive ? '✓' : isCurrent ? '⟳' : '○'}
                </span>
                <span>{step.label}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
