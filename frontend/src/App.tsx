import { useState, useCallback } from 'react'
import Header from './components/Header'
import UploadPanel from './components/UploadPanel'
import ControlPanel from './components/ControlPanel'
import ResultPanel from './components/ResultPanel'
import ProcessingOverlay from './components/ProcessingOverlay'
import Footer from './components/Footer'

export interface UploadState {
  husband: File | null
  wife: File | null
  target: File | null
}

export interface SwapSettings {
  skinToneMatching: boolean
  bodyProportionMatching: boolean
  lightingHarmonization: boolean
  geminiApiKey: string
}

export interface ProcessingResult {
  status: string
  job_id: string
  message: string
  download_url: string
  preview_url: string
  processing_steps: string[]
  gemini_analysis: string | null
  execution_metadata: {
    husband_file: string
    wife_file: string
    target_file: string
    faces_detected: { husband: number; wife: number; target: number }
    skin_tone_matched: boolean
    body_proportions_applied: boolean
    lighting_harmonized: boolean
    ai_engine: string
  }
}

type AppPhase = 'upload' | 'processing' | 'result'

export default function App() {
  const [uploads, setUploads] = useState<UploadState>({
    husband: null,
    wife: null,
    target: null,
  })
  const [settings, setSettings] = useState<SwapSettings>({
    skinToneMatching: true,
    bodyProportionMatching: true,
    lightingHarmonization: true,
    geminiApiKey: '',
  })
  const [phase, setPhase] = useState<AppPhase>('upload')
  const [result, setResult] = useState<ProcessingResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)

  const canProcess = uploads.husband && uploads.wife && uploads.target

  const handleProcess = useCallback(async () => {
    if (!canProcess) return
    setPhase('processing')
    setError(null)
    setProgress(0)

    const formData = new FormData()
    formData.append('husband_face', uploads.husband!)
    formData.append('wife_face', uploads.wife!)
    formData.append('target_couple', uploads.target!)
    formData.append('skin_tone_matching', String(settings.skinToneMatching))
    formData.append('body_proportion_matching', String(settings.bodyProportionMatching))
    formData.append('lighting_harmonization', String(settings.lightingHarmonization))
    if (settings.geminiApiKey) {
      formData.append('gemini_api_key', settings.geminiApiKey)
    }

    // Simulate progress
    const progressInterval = setInterval(() => {
      setProgress((p) => {
        if (p >= 90) {
          clearInterval(progressInterval)
          return 90
        }
        return p + Math.random() * 12
      })
    }, 400)

    try {
      const response = await fetch('/api/antigravity/execute-couple-swap', {
        method: 'POST',
        body: formData,
      })

      clearInterval(progressInterval)

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Processing failed')
      }

      const data: ProcessingResult = await response.json()
      setProgress(100)

      // Small delay to show 100% before switching
      setTimeout(() => {
        setResult(data)
        setPhase('result')
      }, 600)
    } catch (err: unknown) {
      clearInterval(progressInterval)
      const message = err instanceof Error ? err.message : 'An unexpected error occurred'
      setError(message)
      setPhase('upload')
    }
  }, [canProcess, uploads, settings])

  const handleReset = useCallback(() => {
    setUploads({ husband: null, wife: null, target: null })
    setResult(null)
    setPhase('upload')
    setProgress(0)
    setError(null)
  }, [])

  return (
    <>
      <div className="bg-mesh" />

      <div className="min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {phase === 'upload' && (
            <div className="animate-fade-in-up">
              {/* Error Banner */}
              {error && (
                <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 flex items-center gap-3">
                  <span className="text-xl">⚠️</span>
                  <div>
                    <p className="font-semibold">Processing Error</p>
                    <p className="text-sm opacity-80">{error}</p>
                  </div>
                </div>
              )}

              {/* Upload Section */}
              <section className="mb-8">
                <h2
                  className="text-2xl font-bold mb-2"
                  style={{ fontFamily: 'var(--font-display)' }}
                >
                  Upload Your Photos
                </h2>
                <p className="text-[var(--color-ghost)] mb-6">
                  Drop or select the husband's face, wife's face, and the target couple reference image.
                </p>
                <UploadPanel uploads={uploads} setUploads={setUploads} />
              </section>

              {/* Controls & Execute */}
              <section>
                <ControlPanel
                  settings={settings}
                  setSettings={setSettings}
                  canProcess={!!canProcess}
                  onProcess={handleProcess}
                />
              </section>
            </div>
          )}

          {phase === 'processing' && (
            <ProcessingOverlay progress={progress} />
          )}

          {phase === 'result' && result && (
            <ResultPanel
              result={result}
              targetFile={uploads.target}
              onReset={handleReset}
            />
          )}
        </main>

        <Footer />
      </div>
    </>
  )
}
