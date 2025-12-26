/**
 * SubtitleStyler - Shared component for subtitle styling controls
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp, Type } from 'lucide-react'
import FontSelector from './FontSelector'
import SubtitlePreview from './SubtitlePreview'

interface SubtitleStylerProps {
  // Enable/disable
  enabled: boolean
  onEnabledChange: (enabled: boolean) => void

  // Font settings
  font: string
  size: number
  color: string // Hex format (#RRGGBB)
  position: number // Y position from bottom in pixels

  // Border/outline settings
  borderEnabled: boolean
  borderStyle: number // 1 = Outline + Shadow, 3 = Opaque Box
  outlineWidth: number
  outlineColor: string // Hex format

  // Shadow settings
  shadow: number
  shadowColor: string // Hex format

  // Change handlers
  onFontChange: (font: string) => void
  onSizeChange: (size: number) => void
  onColorChange: (color: string) => void
  onPositionChange: (position: number) => void
  onBorderEnabledChange: (enabled: boolean) => void
  onBorderStyleChange: (style: number) => void
  onOutlineWidthChange: (width: number) => void
  onOutlineColorChange: (color: string) => void
  onShadowChange: (shadow: number) => void
  onShadowColorChange: (color: string) => void

  // Preview settings
  text?: string
  language?: string
  isLocalFont?: boolean

  // UI options
  collapsible?: boolean
  defaultExpanded?: boolean
  showPreview?: boolean
}

export default function SubtitleStyler({
  enabled,
  onEnabledChange,
  font,
  size,
  color,
  position,
  borderEnabled,
  borderStyle,
  outlineWidth,
  outlineColor,
  shadow,
  shadowColor,
  onFontChange,
  onSizeChange,
  onColorChange,
  onPositionChange,
  onBorderEnabledChange,
  onBorderStyleChange,
  onOutlineWidthChange,
  onOutlineColorChange,
  onShadowChange,
  onShadowColorChange,
  text = '',
  language = 'en',
  isLocalFont = false,
  collapsible = true,
  defaultExpanded = true,
  showPreview = true,
}: SubtitleStylerProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)

  const content = (
    <div className="space-y-4">
      {/* Enable/Disable */}
      <div className="flex items-center justify-between mt-2">
        <label className="text-sm font-medium text-text-secondary">Enable Subtitles</label>
        <button
          onClick={() => onEnabledChange(!enabled)}
          className={`relative w-12 h-6 rounded-full transition-colors ${
            enabled ? 'bg-green-500' : 'bg-terminal-border'
          }`}
        >
          <span
            className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform shadow-sm ${
              enabled ? 'left-7' : 'left-1'
            }`}
          />
        </button>
      </div>

      {enabled && (
        <>
          {/* Font Selection */}
          <FontSelector selectedFont={font} onFontChange={onFontChange} />

          {/* Size and Position */}
          <div className="grid grid-cols-2 gap-4">
            {/* Font Size */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">
                Size: {size}px
              </label>
              <input
                type="range"
                min="10"
                max="60"
                value={size}
                onChange={(e) => onSizeChange(parseInt(e.target.value))}
                className="w-full h-2 bg-terminal-border rounded-lg appearance-none cursor-pointer accent-accent-primary"
              />
            </div>

            {/* Position */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">
                Position: {position}px
              </label>
              <input
                type="range"
                min="10"
                max="100"
                value={position}
                onChange={(e) => onPositionChange(parseInt(e.target.value))}
                className="w-full h-2 bg-terminal-border rounded-lg appearance-none cursor-pointer accent-accent-primary"
              />
            </div>
          </div>

          {/* Text Color */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Text Color</label>
            <div className="flex gap-2">
              <input
                type="color"
                value={color}
                onChange={(e) => onColorChange(e.target.value)}
                className="w-10 h-10 rounded border border-terminal-border cursor-pointer"
              />
              <input
                type="text"
                value={color}
                onChange={(e) => {
                  const val = e.target.value
                  if (/^#[0-9A-Fa-f]{0,6}$/.test(val)) {
                    onColorChange(val)
                  }
                }}
                className="console-input flex-1"
                placeholder="#FFFFFF"
              />
            </div>
          </div>

          {/* Border/Outline Settings */}
          <div className="border border-terminal-border rounded-lg p-3 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-text-secondary">Border/Outline</label>
              <button
                onClick={() => onBorderEnabledChange(!borderEnabled)}
                className={`relative w-10 h-5 rounded-full transition-colors ${
                  borderEnabled ? 'bg-green-500' : 'bg-terminal-border'
                }`}
              >
                <span
                  className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow-sm ${
                    borderEnabled ? 'left-5' : 'left-0.5'
                  }`}
                />
              </button>
            </div>

            {borderEnabled && (
              <>
                {/* Border Style */}
                <div>
                  <label className="block text-xs text-text-muted mb-1">Style</label>
                  <select
                    value={borderStyle}
                    onChange={(e) => onBorderStyleChange(parseInt(e.target.value))}
                    className="console-input w-full text-sm"
                  >
                    <option value={1}>Outline + Drop Shadow</option>
                    <option value={3}>Opaque Box</option>
                  </select>
                </div>

                {/* Outline Width */}
                <div>
                  <label className="block text-xs text-text-muted mb-1">
                    Outline Width: {outlineWidth.toFixed(1)}px
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="5"
                    step="0.5"
                    value={outlineWidth}
                    onChange={(e) => onOutlineWidthChange(parseFloat(e.target.value))}
                    className="w-full h-2 bg-terminal-border rounded-lg appearance-none cursor-pointer accent-accent-primary"
                  />
                </div>

                {/* Outline Color */}
                <div>
                  <label className="block text-xs text-text-muted mb-1">Outline Color</label>
                  <div className="flex gap-2">
                    <input
                      type="color"
                      value={outlineColor}
                      onChange={(e) => onOutlineColorChange(e.target.value)}
                      className="w-8 h-8 rounded border border-terminal-border cursor-pointer"
                    />
                    <input
                      type="text"
                      value={outlineColor}
                      onChange={(e) => {
                        const val = e.target.value
                        if (/^#[0-9A-Fa-f]{0,6}$/.test(val)) {
                          onOutlineColorChange(val)
                        }
                      }}
                      className="console-input flex-1 text-sm"
                      placeholder="#000000"
                    />
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Shadow Settings */}
          <div className="border border-terminal-border rounded-lg p-3 space-y-3">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">
                Drop Shadow: {shadow.toFixed(1)}px
              </label>
              <input
                type="range"
                min="0"
                max="5"
                step="0.5"
                value={shadow}
                onChange={(e) => onShadowChange(parseFloat(e.target.value))}
                className="w-full h-2 bg-terminal-border rounded-lg appearance-none cursor-pointer accent-accent-primary"
              />
            </div>

            {shadow > 0 && (
              <div>
                <label className="block text-xs text-text-muted mb-1">Shadow Color</label>
                <div className="flex gap-2">
                  <input
                    type="color"
                    value={shadowColor}
                    onChange={(e) => onShadowColorChange(e.target.value)}
                    className="w-8 h-8 rounded border border-terminal-border cursor-pointer"
                  />
                  <input
                    type="text"
                    value={shadowColor}
                    onChange={(e) => {
                      const val = e.target.value
                      if (/^#[0-9A-Fa-f]{0,6}$/.test(val)) {
                        onShadowColorChange(val)
                      }
                    }}
                    className="console-input flex-1 text-sm"
                    placeholder="#000000"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Preview */}
          {showPreview && (
            <SubtitlePreview
              text={text}
              language={language}
              font={font}
              size={size}
              color={color}
              outlineWidth={borderEnabled ? outlineWidth : 0}
              outlineColor={outlineColor}
              shadow={shadow}
              shadowColor={shadowColor}
              isLocalFont={isLocalFont}
            />
          )}
        </>
      )}
    </div>
  )

  if (!collapsible) {
    return content
  }

  return (
    <div className="border border-terminal-border rounded-lg">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-terminal-bg/50 transition-colors"
      >
        <div className="flex items-center gap-2 text-sm">
          <Type className="w-4 h-4 text-accent-primary" />
          <span>Subtitle Settings</span>
          <span className={`text-xs ${enabled ? 'text-green-400' : 'text-text-muted'}`}>
            ({enabled ? 'Enabled' : 'Disabled'})
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-text-muted" />
        ) : (
          <ChevronDown className="w-4 h-4 text-text-muted" />
        )}
      </button>
      {isExpanded && <div className="p-3 pt-0 border-t border-terminal-border">{content}</div>}
    </div>
  )
}
