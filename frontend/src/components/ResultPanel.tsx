import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import {
  Download,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Info,
  CheckCircle,
  AlertTriangle,
  Bot,
} from 'lucide-react'
import type { ProcessingResult } from '../App'

interface ResultPanelProps {
  result: ProcessingResult
  targetFile: File | null
  onReset: () => void
}

/** Before/After comparison slider */
function ComparisonSlider({
  beforeSrc,
  afterSrc,
}: {
  beforeSrc: string
  afterSrc: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState(50)
  const [isDragging, setIsDragging] = useState(false)

  const updatePosition = useCallback(
    (clientX: number) => {
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const x = clientX - rect.left
      const pct = Math.max(0, Math.min(100, (x / rect.width) * 100))
      setPosition(pct)
    },
    []
  )

  useEffect(() => {
    const handleMove = (e: MouseEvent | TouchEvent) => {
      if (!isDragging) return
      e.preventDefault()
      const clientX =
        'touches' in e ? e.touches[0].clientX : e.clientX
      updatePosition(clientX)
    }
    const handleUp = () => setIsDragging(false)

    if (isDragging) {
      window.addEventListener('mousemove', handleMove)
      window.addEventListener('mouseup', handleUp)
      window.addEventListener('touchmove', handleMove, { passive: false })
      window.addEventListener('touchend', handleUp)
    }

    return () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
      window.removeEventListener('touchmove', handleMove)
      window.removeEventListener('touchend', handleUp)
    }
  }, [isDragging, updatePosition])

  return (
    <div
      ref={containerRef}
      className="comparison-container"
      onMouseDown={(e) => {
        setIsDragging(true)
        updatePosition(e.clientX)
      }}
      onTouchStart={(e) => {
        setIsDragging(true)
        updatePosition(e.touches[0].clientX)
      }}
    >
      {/* After (full width underneath) */}
      <img src={afterSrc} alt="After - Processed" className="w-full" />

      {/* Before (clipped) */}
      <div
        className="absolute inset-0 overflow-hidden"
        style={{ width: `${position}%` }}
      >
        <img
          src={beforeSrc}
          alt="Before - Original"
          className="w-full h-full object-cover"
          style={{
            width: containerRef.current
              ? `${containerRef.current.offsetWidth}px`
              : '100%',
          }}
        />
      </div>

      {/* Labels */}
      <div className="absolute top-3 left-3 px-3 py-1 rounded-full text-xs font-semibold text-white bg-black/50 backdrop-blur-sm">
        Before
      </div>
      <div className="absolute top-3 right-3 px-3 py-1 rounded-full text-xs font-semibold text-white bg-[var(--color-uv-start)]/60 backdrop-blur-sm">
        After
      </div>

      {/* Slider Line */}
      <div
        className="comparison-slider-line"
        style={{ left: `${position}%` }}
      >
        <div className="comparison-slider-handle">
          <div className="flex items-center gap-0.5 text-[var(--color-abyss)]">
            <ChevronLeft className="w-3 h-3" />
            <ChevronRight className="w-3 h-3" />
          </div>
        </div>
      </div>
    </div>
  )
}

export default function ResultPanel({
  result,
  targetFile,
  onReset,
}: ResultPanelProps) {
  const [targetPreview, setTargetPreview] = useState<string | null>(null)

  // Generate target preview URL
  useMemo(() => {
    if (targetFile) {
      const reader = new FileReader()
      reader.onloadend = () => setTargetPreview(reader.result as string)
      reader.readAsDataURL(targetFile)
    }
  }, [targetFile])

  const resultImageUrl = result.preview_url

  return (
    <div className="animate-fade-in-up space-y-6">
      {/* Success Banner */}
      <div className="glass-card p-5 flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-[var(--color-success)]/15 flex items-center justify-center flex-shrink-0">
          <CheckCircle className="w-6 h-6 text-[var(--color-success)]" />
        </div>
        <div className="flex-1">
          <h2
            className="text-xl font-bold text-[var(--color-snow)]"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Face Swap Complete!
          </h2>
          <p className="text-sm text-[var(--color-ghost)]">
            Job #{result.job_id} • Engine: {result.execution_metadata.ai_engine}
          </p>
        </div>
        <div className="flex gap-3">
          <a
            href={result.download_url}
            download
            className="btn-primary !py-2.5 !px-5 !text-sm"
          >
            <span className="flex items-center gap-2">
              <Download className="w-4 h-4" />
              Download
            </span>
          </a>
          <button
            onClick={onReset}
            className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-full border border-[rgba(99,102,241,0.2)] text-[var(--color-ghost)] hover:text-[var(--color-snow)] hover:border-[rgba(99,102,241,0.4)] transition-all"
          >
            <RotateCcw className="w-4 h-4" />
            New Swap
          </button>
        </div>
      </div>

      {/* Comparison Slider */}
      <div className="glass-card p-5">
        <h3
          className="text-lg font-semibold mb-4 flex items-center gap-2"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          <span className="w-2 h-2 rounded-full bg-[var(--color-uv-start)]" />
          Before / After Comparison
        </h3>
        {targetPreview ? (
          <div className="result-glow rounded-xl">
            <ComparisonSlider
              beforeSrc={targetPreview}
              afterSrc={resultImageUrl}
            />
          </div>
        ) : (
          <div className="rounded-xl overflow-hidden result-glow">
            <img
              src={resultImageUrl}
              alt="Processed result"
              className="w-full"
            />
          </div>
        )}
      </div>

      {/* Processing Steps & Metadata */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Steps */}
        <div className="glass-card p-5">
          <h3
            className="text-base font-semibold mb-3 flex items-center gap-2"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            <Info className="w-4 h-4 text-[var(--color-uv-start)]" />
            Processing Pipeline
          </h3>
          <div className="space-y-1">
            {result.processing_steps.map((step, i) => (
              <div key={i} className="step-item">
                {step.startsWith('✅') ? (
                  <CheckCircle className="w-4 h-4 text-[var(--color-success)] flex-shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-[var(--color-warning)] flex-shrink-0" />
                )}
                <span>{step.replace(/^[✅⚠️]\s*/, '')}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Metadata */}
        <div className="glass-card p-5">
          <h3
            className="text-base font-semibold mb-3 flex items-center gap-2"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            <Bot className="w-4 h-4 text-[var(--color-cyan-start)]" />
            Execution Metadata
          </h3>
          <div className="space-y-2 text-sm">
            {[
              ['Husband File', result.execution_metadata.husband_file],
              ['Wife File', result.execution_metadata.wife_file],
              ['Target File', result.execution_metadata.target_file],
              [
                'Faces Detected',
                `H: ${result.execution_metadata.faces_detected.husband} / W: ${result.execution_metadata.faces_detected.wife} / T: ${result.execution_metadata.faces_detected.target}`,
              ],
              [
                'Skin Tone',
                result.execution_metadata.skin_tone_matched ? 'Applied' : 'Skipped',
              ],
              [
                'Body Proportions',
                result.execution_metadata.body_proportions_applied
                  ? 'Applied'
                  : 'Skipped',
              ],
              [
                'Lighting',
                result.execution_metadata.lighting_harmonized
                  ? 'Applied'
                  : 'Skipped',
              ],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between items-center">
                <span className="text-[var(--color-ghost)]">{label}</span>
                <span className="text-[var(--color-snow)] font-medium truncate ml-4 max-w-[200px] text-right">
                  {value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Gemini Analysis */}
      {result.gemini_analysis && (
        <div className="glass-card p-5 animate-fade-in-up delay-300">
          <h3
            className="text-base font-semibold mb-3 flex items-center gap-2"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            <span className="text-lg">✨</span>
            Gemini Pro Vision Analysis
          </h3>
          <p className="text-sm text-[var(--color-mist)] leading-relaxed whitespace-pre-wrap">
            {result.gemini_analysis}
          </p>
        </div>
      )}
    </div>
  )
}
