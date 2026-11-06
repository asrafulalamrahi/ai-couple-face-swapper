import { useRef, useState, useCallback } from 'react'
import { Upload, User, Heart, Image, X, Check } from 'lucide-react'
import type { UploadState } from '../App'

interface UploadPanelProps {
  uploads: UploadState
  setUploads: React.Dispatch<React.SetStateAction<UploadState>>
}

interface DropzoneConfig {
  key: keyof UploadState
  label: string
  sublabel: string
  icon: React.ReactNode
  accentFrom: string
  accentTo: string
}

const dropzones: DropzoneConfig[] = [
  {
    key: 'husband',
    label: "Husband's Face",
    sublabel: 'Source face photo — will be mapped to the male subject',
    icon: <User className="w-8 h-8" />,
    accentFrom: '#6366f1',
    accentTo: '#8b5cf6',
  },
  {
    key: 'wife',
    label: "Wife's Face",
    sublabel: 'Source face photo — will be mapped to the female subject',
    icon: <Heart className="w-8 h-8" />,
    accentFrom: '#ec4899',
    accentTo: '#f43f5e',
  },
  {
    key: 'target',
    label: 'Target Couple',
    sublabel: 'Reference image — pose, clothing, and background preserved',
    icon: <Image className="w-8 h-8" />,
    accentFrom: '#06b6d4',
    accentTo: '#22d3ee',
  },
]

function DropzoneCard({
  config,
  file,
  onFile,
  onClear,
}: {
  config: DropzoneConfig
  file: File | null
  onFile: (f: File) => void
  onClear: () => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)

  const handleFile = useCallback(
    (f: File) => {
      if (!f.type.startsWith('image/')) return
      onFile(f)
      const reader = new FileReader()
      reader.onloadend = () => setPreview(reader.result as string)
      reader.readAsDataURL(f)
    },
    [onFile]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragActive(false)
      const f = e.dataTransfer.files[0]
      if (f) handleFile(f)
    },
    [handleFile]
  )

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0]
      if (f) handleFile(f)
    },
    [handleFile]
  )

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onClear()
      setPreview(null)
      if (inputRef.current) inputRef.current.value = ''
    },
    [onClear]
  )

  return (
    <div
      className={`dropzone relative ${dragActive ? 'active' : ''} ${file ? 'has-file' : ''}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault()
        setDragActive(true)
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={handleDrop}
      style={{ minHeight: '240px' }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleChange}
      />

      {preview && file ? (
        <div className="relative w-full h-full min-h-[200px]">
          <img
            src={preview}
            alt={config.label}
            className="preview-image absolute inset-0 w-full h-full"
          />
          {/* Overlay with file info */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent rounded-[calc(var(--radius-xl)-4px)] flex flex-col justify-end p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-[var(--color-success)]" />
                <span className="text-sm font-medium text-white truncate max-w-[150px]">
                  {file.name}
                </span>
              </div>
              <button
                onClick={handleClear}
                className="w-7 h-7 rounded-full bg-white/15 hover:bg-red-500/60 flex items-center justify-center transition-colors backdrop-blur-sm"
                title="Remove"
              >
                <X className="w-3.5 h-3.5 text-white" />
              </button>
            </div>
            <p className="text-xs text-white/60 mt-1">
              {(file.size / 1024).toFixed(0)} KB
            </p>
          </div>
          {/* Label badge */}
          <div
            className="absolute top-3 left-3 px-3 py-1 rounded-full text-xs font-semibold text-white backdrop-blur-md"
            style={{
              background: `linear-gradient(135deg, ${config.accentFrom}cc, ${config.accentTo}cc)`,
            }}
          >
            {config.label}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4 py-6 relative z-10">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center"
            style={{
              background: `linear-gradient(135deg, ${config.accentFrom}20, ${config.accentTo}20)`,
              color: config.accentFrom,
            }}
          >
            {config.icon}
          </div>
          <div>
            <p
              className="text-base font-semibold text-[var(--color-snow)]"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              {config.label}
            </p>
            <p className="text-xs text-[var(--color-ghost)] mt-1 max-w-[200px] mx-auto">
              {config.sublabel}
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-[var(--color-ghost)]">
            <Upload className="w-3.5 h-3.5" />
            <span>Drop image or click to browse</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default function UploadPanel({ uploads, setUploads }: UploadPanelProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      {dropzones.map((config, idx) => (
        <div
          key={config.key}
          className="animate-fade-in-up"
          style={{ animationDelay: `${idx * 0.1}s`, opacity: 0 }}
        >
          <DropzoneCard
            config={config}
            file={uploads[config.key]}
            onFile={(f) =>
              setUploads((prev) => ({ ...prev, [config.key]: f }))
            }
            onClear={() =>
              setUploads((prev) => ({ ...prev, [config.key]: null }))
            }
          />
        </div>
      ))}
    </div>
  )
}
