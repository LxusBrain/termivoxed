/**
 * TTSConsentModal - Privacy consent dialog for Text-to-Speech
 *
 * Shows when user first attempts to use TTS features.
 * Explains that text is sent to Microsoft's servers.
 */

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  Upload,
  Shield,
  ExternalLink,
  Check,
  X,
  FileText,
  Loader2,
} from 'lucide-react';
import { useConsentStore } from '../stores/consentStore';

export default function TTSConsentModal() {
  const {
    showTTSConsentModal,
    closeTTSConsentModal,
    recordTTSConsent,
    ttsDialogContent,
    loadTTSDialogContent,
    isLoading,
    error,
  } = useConsentStore();

  // Load dialog content when modal opens
  useEffect(() => {
    if (showTTSConsentModal && !ttsDialogContent) {
      loadTTSDialogContent();
    }
  }, [showTTSConsentModal, ttsDialogContent, loadTTSDialogContent]);

  const handleAccept = async () => {
    await recordTTSConsent(true);
  };

  const handleDecline = async () => {
    await recordTTSConsent(false);
  };

  if (!showTTSConsentModal) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <div
          className="absolute inset-0 bg-black/80"
          onClick={closeTTSConsentModal}
        />

        {/* Modal */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative bg-terminal-surface border border-terminal-border rounded-lg w-full max-w-xl max-h-[90vh] flex flex-col overflow-hidden"
        >
          {/* Header with warning color */}
          <div className="bg-gradient-to-r from-amber-600/20 to-orange-600/20 border-b border-amber-500/30 px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500/20 rounded-lg">
                <AlertTriangle className="w-6 h-6 text-amber-500" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-text-primary">
                  Text-to-Speech Privacy Notice
                </h2>
                <p className="text-sm text-amber-400/80">
                  External data processing required
                </p>
              </div>
            </div>
          </div>

          {/* Scrollable content */}
          <div className="flex-1 overflow-y-auto p-6">
            <div className="space-y-5">
              {/* Introduction */}
              <p className="text-text-secondary">
                Voice generation requires sending your script text to external servers.
                Please review the following information before enabling this feature.
              </p>

              {/* Warning Banner */}
              <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
                <div className="flex items-start gap-3">
                  <Shield className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                  <div className="text-sm">
                    <p className="text-amber-400 font-medium mb-1">
                      Important Privacy Information
                    </p>
                    <p className="text-text-muted">
                      Your script content will be transmitted to Microsoft's servers.
                      This data may be logged and retained according to Microsoft's policies.
                    </p>
                  </div>
                </div>
              </div>

              {/* What data is sent */}
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
                  <Upload className="w-4 h-4 text-accent-red" />
                  What data is sent?
                </h3>
                <ul className="text-sm text-text-muted space-y-1 ml-6">
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-text-muted rounded-full" />
                    Your script/subtitle text
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-text-muted rounded-full" />
                    Selected voice and language
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-text-muted rounded-full" />
                    Speech parameters (rate, pitch, volume)
                  </li>
                </ul>
              </div>

              {/* Where it's sent */}
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
                  <FileText className="w-4 h-4 text-accent-red" />
                  Where is it sent?
                </h3>
                <div className="text-sm text-text-muted ml-6 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-text-primary font-medium">Provider:</span>
                    <span>Microsoft Edge Text-to-Speech</span>
                  </div>
                  <p className="text-text-muted/80 text-xs">
                    This service is provided by Microsoft. We do not control how
                    Microsoft processes, stores, or uses your data.
                  </p>
                  <a
                    href="https://privacy.microsoft.com/privacystatement"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-accent-red hover:text-accent-red-light text-xs"
                  >
                    View Microsoft Privacy Policy
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>

              {/* Recommendations */}
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-text-primary">
                  Recommendations
                </h3>
                <div className="p-3 rounded bg-terminal-bg border border-terminal-border">
                  <ul className="text-xs text-text-muted space-y-1.5">
                    <li className="flex items-start gap-2">
                      <X className="w-3.5 h-3.5 text-red-500 shrink-0 mt-0.5" />
                      <span>Do not include passwords or API keys in scripts</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <X className="w-3.5 h-3.5 text-red-500 shrink-0 mt-0.5" />
                      <span>Avoid personal information (names, addresses, phone numbers)</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <X className="w-3.5 h-3.5 text-red-500 shrink-0 mt-0.5" />
                      <span>Do not include confidential business information</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <Check className="w-3.5 h-3.5 text-green-500 shrink-0 mt-0.5" />
                      <span>Review scripts before generating audio</span>
                    </li>
                  </ul>
                </div>
              </div>

              {/* Error message */}
              {error && (
                <div className="p-3 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                  {error}
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="p-6 pt-4 border-t border-terminal-border bg-terminal-bg/50">
            <p className="text-xs text-text-muted mb-4">
              You can change this setting anytime in Settings &gt; Privacy.
              Declining will disable voice generation features.
            </p>

            <div className="flex items-center justify-between gap-3">
              <button
                onClick={handleDecline}
                disabled={isLoading}
                className="btn-secondary flex-1"
              >
                No Thanks
              </button>
              <button
                onClick={handleAccept}
                disabled={isLoading}
                className="btn-primary flex-1 flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    I Understand, Enable TTS
                  </>
                )}
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

/**
 * TTSWarningBanner - Inline warning shown in voice/audio sections
 *
 * Only shows for cloud providers (Edge TTS) that send data externally.
 * Hidden for local providers (Coqui) that process everything locally.
 */
export function TTSWarningBanner({
  onShowDetails,
  compact = false,
  provider,
}: {
  onShowDetails?: () => void;
  compact?: boolean;
  provider?: string;
}) {
  const { hasTTSConsent, preferredProvider } = useConsentStore();

  // Determine the active provider
  const activeProvider = provider || preferredProvider || 'edge_tts';

  // Local providers don't send data externally - no warning needed
  const LOCAL_PROVIDERS = ['coqui', 'piper'];
  if (LOCAL_PROVIDERS.includes(activeProvider.toLowerCase())) {
    return null;
  }

  // Only show for cloud providers if consent has been granted
  if (!hasTTSConsent) return null;

  if (compact) {
    return (
      <div className="flex items-center gap-1.5 text-[10px] text-amber-500/70">
        <Upload className="w-3 h-3" />
        <span>Text sent to Microsoft</span>
        {onShowDetails && (
          <button
            onClick={onShowDetails}
            className="underline hover:text-amber-400"
          >
            Info
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="p-2 rounded bg-amber-500/5 border border-amber-500/20">
      <div className="flex items-center gap-2">
        <Upload className="w-3.5 h-3.5 text-amber-500/70 shrink-0" />
        <div className="flex-1 min-w-0">
          <span className="text-[11px] text-amber-500/70">
            Text is sent to Microsoft for voice generation.
            Avoid sensitive content.
          </span>
        </div>
        {onShowDetails && (
          <button
            onClick={onShowDetails}
            className="text-[10px] text-amber-500 hover:text-amber-400 underline shrink-0"
          >
            Privacy Info
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * TTSConsentRequired - Placeholder shown when TTS consent is not granted
 *
 * Prompts user to enable TTS.
 */
export function TTSConsentRequired({
  onRequestConsent,
}: {
  onRequestConsent: () => void;
}) {
  return (
    <div className="p-4 rounded-lg bg-terminal-bg border border-terminal-border text-center">
      <Upload className="w-8 h-8 text-text-muted mx-auto mb-3" />
      <h4 className="text-sm font-medium text-text-primary mb-1">
        Voice Generation Disabled
      </h4>
      <p className="text-xs text-text-muted mb-3">
        Enable text-to-speech to preview and generate voice-overs.
        Your text will be sent to Microsoft's servers.
      </p>
      <button
        onClick={onRequestConsent}
        className="btn-secondary text-sm"
      >
        Enable Text-to-Speech
      </button>
    </div>
  );
}
