import {
  Paintbrush,
  Move3d,
  Sun,
  Key,
  Zap,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { useState } from 'react'
import type { SwapSettings } from '../App'

interface ControlPanelProps {
  settings: SwapSettings
  setSettings: React.Dispatch<React.SetStateAction<SwapSettings>>
  canProcess: boolean
  onProcess: () => void
}

function Toggle({
  active,
  onToggle,
}: {
  active: boolean
  onToggle: () => void
}) {
  return (
    <div
      className={`toggle-track ${active ? 'active' : ''}`}
      onClick={onToggle}
      role="switch"
      aria-checked={active}
    >
      <div className="toggle-thumb" />
    </div>
  )
}

export default function ControlPanel({
  settings,
  setSettings,
  canProcess,
  onProcess,
}: ControlPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)

  const toggles = [
    {
      key: 'skinToneMatching' as const,
      label: 'Skin Tone Matching',
      description: 'LAB color space harmonization for natural skin blending',
      icon: <Paintbrush className="w-4.5 h-4.5" />,
      color: '#ec4899',
    },
    {
      key: 'bodyProportionMatching' as const,
      label: 'Body Proportion Matching',
      description: 'Adjusts silhouette to match target body proportions',
      icon: <Move3d className="w-4.5 h-4.5" />,
      color: '#8b5cf6',
    },
    {
      key: 'lightingHarmonization' as const,
      label: 'Lighting Harmonization',
      description: 'Matches brightness and contrast to the target scene',
      icon: <Sun className="w-4.5 h-4.5" />,
      color: '#f59e0b',
    },
  ]

  return (
    <div className="glass-card p-6 animate-fade-in-up delay-400">
      {/* Processing Toggles */}
      <div className="flex items-center gap-2 mb-5">
        <Zap className="w-5 h-5 text-[var(--color-uv-start)]" />
        <h3
          className="text-lg font-semibold"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          Processing Settings
        </h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {toggles.map((t) => (
          <div
            key={t.key}
            className="flex items-start gap-3 p-3 rounded-xl bg-[rgba(99,102,241,0.04)] border border-[rgba(99,102,241,0.08)] hover:border-[rgba(99,102,241,0.2)] transition-colors"
          >
            <div
              className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
              style={{ background: `${t.color}18`, color: t.color }}
            >
              {t.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2 mb-1">
                <p className="text-sm font-medium text-[var(--color-snow)] truncate">
                  {t.label}
                </p>
                <Toggle
                  active={settings[t.key]}
                  onToggle={() =>
                    setSettings((prev) => ({
                      ...prev,
                      [t.key]: !prev[t.key],
                    }))
                  }
                />
              </div>
              <p className="text-xs text-[var(--color-ghost)] leading-relaxed">
                {t.description}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Advanced: Gemini API Key */}
      <div className="mb-6">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-2 text-sm text-[var(--color-ghost)] hover:text-[var(--color-uv-glow)] transition-colors"
        >
          {showAdvanced ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
          <Key className="w-3.5 h-3.5" />
          Advanced: Gemini Pro Vision API
        </button>

        {showAdvanced && (
          <div className="mt-3 animate-fade-in">
            <div className="flex items-center gap-3">
              <input
                type="password"
                placeholder="Enter your Gemini API key (optional)"
                value={settings.geminiApiKey}
                onChange={(e) =>
                  setSettings((prev) => ({
                    ...prev,
                    geminiApiKey: e.target.value,
                  }))
                }
                className="flex-1 px-4 py-2.5 rounded-xl bg-[rgba(99,102,241,0.06)] border border-[rgba(99,102,241,0.15)] text-sm text-[var(--color-snow)] placeholder:text-[var(--color-ghost)] focus:outline-none focus:border-[var(--color-uv-start)] focus:ring-1 focus:ring-[var(--color-uv-start)] transition-all"
              />
            </div>
            <p className="text-xs text-[var(--color-ghost)] mt-2">
              When provided, Gemini Pro Vision will analyze the result quality and suggest improvements.
            </p>
          </div>
        )}
      </div>

      {/* Execute Button */}
      <div className="flex justify-center">
        <button
          className="btn-primary"
          disabled={!canProcess}
          onClick={onProcess}
        >
          <span className="flex items-center gap-3">
            <Zap className="w-5 h-5" />
            Execute Antigravity Face Swap
          </span>
        </button>
      </div>

      {!canProcess && (
        <p className="text-center text-xs text-[var(--color-ghost)] mt-3">
          Upload all three photos to enable processing
        </p>
      )}
    </div>
  )
}
