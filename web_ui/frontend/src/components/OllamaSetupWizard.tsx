/**
 * OllamaSetupWizard - Multi-step wizard for setting up local AI (Ollama)
 *
 * Guides users through:
 * 1. Installation check
 * 2. Installing Ollama
 * 3. Consenting to local AI processing
 * 4. Downloading recommended models
 */

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Download,
  Check,
  X,
  ExternalLink,
  Loader2,
  Cpu,
  HardDrive,
  Shield,
  Server,
  RefreshCw,
  AlertCircle,
  ChevronRight,
  Sparkles,
  Eye,
} from 'lucide-react';
import {
  useOllamaStore,
  type OllamaStatus,
  type InstallInstructions,
  type RecommendedModel,
  type ModelDownloadProgress,
} from '../stores/ollamaStore';

export default function OllamaSetupWizard() {
  const {
    showSetupWizard,
    closeSetupWizard,
    wizardStep,
    setWizardStep,
    status,
    consent,
    installInstructions,
    recommendedModels,
    isLoading,
    error,
    downloadingModel,
    downloadProgress,
    checkStatus,
    grantConsent,
    pullModel,
    openDownloadPage,
  } = useOllamaStore();

  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [acknowledgedItems, setAcknowledgedItems] = useState<string[]>([]);

  // Refresh status periodically when on install step
  useEffect(() => {
    if (showSetupWizard && wizardStep === 'install') {
      const interval = setInterval(() => {
        checkStatus();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [showSetupWizard, wizardStep, checkStatus]);

  // Auto-advance when Ollama becomes available
  useEffect(() => {
    if (wizardStep === 'install' && status?.running) {
      setWizardStep('consent');
    }
  }, [status?.running, wizardStep, setWizardStep]);

  // Auto-advance when consent is granted
  useEffect(() => {
    if (wizardStep === 'consent' && consent?.consented) {
      setWizardStep('models');
    }
  }, [consent?.consented, wizardStep, setWizardStep]);

  if (!showSetupWizard) return null;

  const handleConsentChange = (item: string) => {
    setAcknowledgedItems((prev) =>
      prev.includes(item) ? prev.filter((i) => i !== item) : [...prev, item]
    );
  };

  const handleGrantConsent = async () => {
    if (acknowledgedItems.length === 4) {
      await grantConsent(acknowledgedItems);
    }
  };

  const handleDownloadModel = async () => {
    if (selectedModel) {
      const success = await pullModel(selectedModel);
      if (success) {
        setWizardStep('complete');
      }
    }
  };

  const handleSkipModels = () => {
    setWizardStep('complete');
  };

  const handleComplete = () => {
    closeSetupWizard();
  };

  const renderStep = () => {
    switch (wizardStep) {
      case 'check':
        return <CheckStep onNext={() => setWizardStep('install')} />;
      case 'install':
        return (
          <InstallStep
            status={status}
            instructions={installInstructions}
            onOpenDownload={openDownloadPage}
            onRefresh={checkStatus}
            onNext={() => setWizardStep('consent')}
            isLoading={isLoading}
          />
        );
      case 'consent':
        return (
          <ConsentStep
            acknowledgedItems={acknowledgedItems}
            onToggle={handleConsentChange}
            onGrant={handleGrantConsent}
            isLoading={isLoading}
            error={error}
          />
        );
      case 'models':
        return (
          <ModelsStep
            recommendedModels={recommendedModels}
            installedModels={status?.models || []}
            selectedModel={selectedModel}
            onSelectModel={setSelectedModel}
            onDownload={handleDownloadModel}
            onSkip={handleSkipModels}
            downloadingModel={downloadingModel}
            downloadProgress={downloadProgress}
            isLoading={isLoading}
          />
        );
      case 'complete':
        return <CompleteStep onFinish={handleComplete} />;
      default:
        return null;
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <div className="absolute inset-0 bg-black/80" />

        {/* Modal */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative bg-terminal-surface border border-terminal-border rounded-lg w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="bg-gradient-to-r from-purple-600/20 to-indigo-600/20 border-b border-purple-500/30 px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-500/20 rounded-lg">
                <Sparkles className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-text-primary">
                  Local AI Setup
                </h2>
                <p className="text-sm text-purple-400/80">
                  Set up Ollama for local AI features
                </p>
              </div>
            </div>

            {/* Progress indicators */}
            <div className="flex items-center gap-2 mt-4">
              {(['check', 'install', 'consent', 'models', 'complete'] as const).map((step: string, index: number) => (
                <div key={step} className="flex items-center">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      wizardStep === step
                        ? 'bg-purple-500'
                        : ['check', 'install', 'consent', 'models', 'complete'].indexOf(wizardStep) > index
                        ? 'bg-green-500'
                        : 'bg-terminal-border'
                    }`}
                  />
                  {index < 4 && (
                    <div
                      className={`w-8 h-0.5 ${
                        ['check', 'install', 'consent', 'models', 'complete'].indexOf(wizardStep) > index
                          ? 'bg-green-500'
                          : 'bg-terminal-border'
                      }`}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">{renderStep()}</div>

          {/* Close button */}
          <button
            onClick={closeSetupWizard}
            className="absolute top-4 right-4 p-1 text-text-muted hover:text-text-primary"
          >
            <X className="w-5 h-5" />
          </button>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

// Step Components

function CheckStep({ onNext }: { onNext: () => void }) {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <Cpu className="w-16 h-16 text-purple-400 mx-auto mb-4" />
        <h3 className="text-xl font-semibold text-text-primary mb-2">
          Enable Local AI Features
        </h3>
        <p className="text-text-secondary max-w-md mx-auto">
          TermiVoxed can use Ollama to run AI models locally on your computer.
          This means faster processing and complete privacy - your data never leaves your machine.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-terminal-bg rounded-lg border border-terminal-border">
          <Shield className="w-8 h-8 text-green-400 mb-2" />
          <h4 className="font-medium text-text-primary mb-1">100% Private</h4>
          <p className="text-xs text-text-muted">
            All processing happens locally. No data is sent to external servers.
          </p>
        </div>
        <div className="p-4 bg-terminal-bg rounded-lg border border-terminal-border">
          <Server className="w-8 h-8 text-blue-400 mb-2" />
          <h4 className="font-medium text-text-primary mb-1">Works Offline</h4>
          <p className="text-xs text-text-muted">
            Once set up, works without internet connection.
          </p>
        </div>
        <div className="p-4 bg-terminal-bg rounded-lg border border-terminal-border">
          <Sparkles className="w-8 h-8 text-purple-400 mb-2" />
          <h4 className="font-medium text-text-primary mb-1">Free Forever</h4>
          <p className="text-xs text-text-muted">
            No API costs or usage limits. Run as much as you want.
          </p>
        </div>
      </div>

      <div className="flex justify-center">
        <button onClick={onNext} className="btn-primary flex items-center gap-2">
          Get Started
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

interface InstallStepProps {
  status: OllamaStatus | null;
  instructions: InstallInstructions | null;
  onOpenDownload: () => void;
  onRefresh: () => void;
  onNext: () => void;
  isLoading: boolean;
}

function InstallStep({
  status,
  instructions,
  onOpenDownload,
  onRefresh,
  onNext,
  isLoading,
}: InstallStepProps) {
  if (status?.running) {
    return (
      <div className="text-center space-y-4">
        <div className="p-4 bg-green-500/10 rounded-full w-fit mx-auto">
          <Check className="w-12 h-12 text-green-500" />
        </div>
        <h3 className="text-xl font-semibold text-text-primary">Ollama is Running!</h3>
        <p className="text-text-secondary">
          Version {status.version || 'unknown'} detected
        </p>
        <button onClick={onNext} className="btn-primary flex items-center gap-2 mx-auto">
          Continue
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    );
  }

  if (status?.installed && !status?.running) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-text-primary mb-2">
            Ollama is Installed but Not Running
          </h3>
          <p className="text-text-secondary">
            Please start Ollama to continue. {instructions?.post_install}
          </p>
        </div>

        <div className="flex justify-center gap-3">
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Check Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <Download className="w-12 h-12 text-purple-400 mx-auto mb-4" />
        <h3 className="text-xl font-semibold text-text-primary mb-2">
          Install Ollama
        </h3>
        <p className="text-text-secondary">
          Ollama is required to run AI models locally.
        </p>
      </div>

      {instructions && (
        <div className="bg-terminal-bg rounded-lg border border-terminal-border p-4">
          <h4 className="font-medium text-text-primary mb-3">
            Installation Steps for {instructions.platform}:
          </h4>
          <ol className="space-y-2">
            {instructions.steps.map((step, index) => (
              <li key={index} className="flex items-start gap-3 text-sm text-text-secondary">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-xs">
                  {index + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>

          {instructions.command && (
            <div className="mt-4 p-3 bg-black/50 rounded border border-terminal-border">
              <p className="text-xs text-text-muted mb-1">Or install via command line:</p>
              <code className="text-sm text-green-400 font-mono">
                {instructions.command}
              </code>
            </div>
          )}
        </div>
      )}

      <div className="flex justify-center gap-3">
        <button
          onClick={onOpenDownload}
          className="btn-primary flex items-center gap-2"
        >
          <ExternalLink className="w-4 h-4" />
          Download Ollama
        </button>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Check Again
        </button>
      </div>
    </div>
  );
}

interface ConsentStepProps {
  acknowledgedItems: string[];
  onToggle: (item: string) => void;
  onGrant: () => void;
  isLoading: boolean;
  error: string | null;
}

function ConsentStep({ acknowledgedItems, onToggle, onGrant, isLoading, error }: ConsentStepProps) {
  const consentItems = [
    {
      id: 'local_processing',
      title: 'Local Processing',
      description: 'AI models will run on your computer, using your CPU/GPU',
    },
    {
      id: 'model_storage',
      title: 'Model Storage',
      description: 'Models will be stored locally (2-8 GB per model)',
    },
    {
      id: 'resource_usage',
      title: 'Resource Usage',
      description: 'Running models uses CPU/GPU and RAM during inference',
    },
    {
      id: 'no_cloud',
      title: 'No Cloud Processing',
      description: 'Your data stays on your machine - nothing is sent externally',
    },
  ];

  const allAcknowledged = acknowledgedItems.length === 4;

  return (
    <div className="space-y-6">
      <div className="text-center">
        <Shield className="w-12 h-12 text-purple-400 mx-auto mb-4" />
        <h3 className="text-xl font-semibold text-text-primary mb-2">
          Local AI Consent
        </h3>
        <p className="text-text-secondary">
          Please acknowledge the following before enabling local AI features.
        </p>
      </div>

      <div className="space-y-3">
        {consentItems.map((item) => (
          <label
            key={item.id}
            className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
              acknowledgedItems.includes(item.id)
                ? 'bg-purple-500/10 border-purple-500/50'
                : 'bg-terminal-bg border-terminal-border hover:border-purple-500/30'
            }`}
          >
            <input
              type="checkbox"
              checked={acknowledgedItems.includes(item.id)}
              onChange={() => onToggle(item.id)}
              className="mt-1"
            />
            <div>
              <p className="font-medium text-text-primary">{item.title}</p>
              <p className="text-sm text-text-muted">{item.description}</p>
            </div>
          </label>
        ))}
      </div>

      {error && (
        <div className="p-3 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="flex justify-center">
        <button
          onClick={onGrant}
          disabled={!allAcknowledged || isLoading}
          className="btn-primary flex items-center gap-2"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Check className="w-4 h-4" />
              I Understand, Enable Local AI
            </>
          )}
        </button>
      </div>
    </div>
  );
}

interface ModelsStepProps {
  recommendedModels: { text: RecommendedModel[]; vision: RecommendedModel[] } | null;
  installedModels: string[];
  selectedModel: string | null;
  onSelectModel: (model: string) => void;
  onDownload: () => void;
  onSkip: () => void;
  downloadingModel: string | null;
  downloadProgress: ModelDownloadProgress | null;
  isLoading: boolean;
}

function ModelsStep({
  recommendedModels,
  installedModels,
  selectedModel,
  onSelectModel,
  onDownload,
  onSkip,
  downloadingModel,
  downloadProgress,
  isLoading,
}: ModelsStepProps) {
  const isDownloading = !!downloadingModel;
  const progressPercent =
    downloadProgress?.total && downloadProgress?.completed
      ? Math.round((downloadProgress.completed / downloadProgress.total) * 100)
      : 0;

  return (
    <div className="space-y-6">
      <div className="text-center">
        <HardDrive className="w-12 h-12 text-purple-400 mx-auto mb-4" />
        <h3 className="text-xl font-semibold text-text-primary mb-2">
          Download a Model
        </h3>
        <p className="text-text-secondary">
          Choose a model to download. You can add more models later.
        </p>
      </div>

      {/* Download progress */}
      {isDownloading && (
        <div className="bg-terminal-bg rounded-lg border border-terminal-border p-4">
          <div className="flex items-center gap-3 mb-2">
            <Loader2 className="w-5 h-5 text-purple-400 animate-spin" />
            <span className="text-text-primary font-medium">
              Downloading {downloadingModel}...
            </span>
          </div>
          <div className="w-full bg-terminal-border rounded-full h-2">
            <div
              className="bg-purple-500 h-2 rounded-full transition-all"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <p className="text-xs text-text-muted mt-2">
            {downloadProgress?.status || 'Downloading...'} - {progressPercent}%
          </p>
        </div>
      )}

      {/* Text Models */}
      {!isDownloading && (
        <>
          <div>
            <h4 className="text-sm font-medium text-text-primary mb-2 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-400" />
              Text Models (Script Generation)
            </h4>
            <div className="space-y-2">
              {recommendedModels?.text.map((model: RecommendedModel) => {
                const isInstalled = installedModels.some((m: string) =>
                  m.toLowerCase().includes(model.name.split(':')[0].toLowerCase())
                );
                return (
                  <label
                    key={model.name}
                    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedModel === model.name
                        ? 'bg-purple-500/10 border-purple-500/50'
                        : 'bg-terminal-bg border-terminal-border hover:border-purple-500/30'
                    } ${isInstalled ? 'opacity-50' : ''}`}
                  >
                    <input
                      type="radio"
                      name="model"
                      value={model.name}
                      checked={selectedModel === model.name}
                      onChange={() => !isInstalled && onSelectModel(model.name)}
                      disabled={isInstalled}
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-text-primary">{model.name}</span>
                        {isInstalled && (
                          <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded">
                            Installed
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-text-muted">{model.description}</p>
                      <p className="text-xs text-text-muted mt-1">
                        Size: {model.size} | VRAM: {model.vram}
                      </p>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Vision Models */}
          <div>
            <h4 className="text-sm font-medium text-text-primary mb-2 flex items-center gap-2">
              <Eye className="w-4 h-4 text-blue-400" />
              Vision Models (Video Analysis)
            </h4>
            <div className="space-y-2">
              {recommendedModels?.vision.map((model: RecommendedModel) => {
                const isInstalled = installedModels.some((m: string) =>
                  m.toLowerCase().includes(model.name.split(':')[0].toLowerCase())
                );
                return (
                  <label
                    key={model.name}
                    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedModel === model.name
                        ? 'bg-purple-500/10 border-purple-500/50'
                        : 'bg-terminal-bg border-terminal-border hover:border-purple-500/30'
                    } ${isInstalled ? 'opacity-50' : ''}`}
                  >
                    <input
                      type="radio"
                      name="model"
                      value={model.name}
                      checked={selectedModel === model.name}
                      onChange={() => !isInstalled && onSelectModel(model.name)}
                      disabled={isInstalled}
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-text-primary">{model.name}</span>
                        {isInstalled && (
                          <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded">
                            Installed
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-text-muted">{model.description}</p>
                      <p className="text-xs text-text-muted mt-1">
                        Size: {model.size} | VRAM: {model.vram}
                      </p>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>
        </>
      )}

      <div className="flex justify-center gap-3">
        {!isDownloading && (
          <>
            <button onClick={onSkip} className="btn-secondary">
              Skip for Now
            </button>
            <button
              onClick={onDownload}
              disabled={!selectedModel || isLoading}
              className="btn-primary flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Download Selected Model
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function CompleteStep({ onFinish }: { onFinish: () => void }) {
  return (
    <div className="text-center space-y-6">
      <div className="p-4 bg-green-500/10 rounded-full w-fit mx-auto">
        <Check className="w-16 h-16 text-green-500" />
      </div>

      <div>
        <h3 className="text-2xl font-semibold text-text-primary mb-2">
          Setup Complete!
        </h3>
        <p className="text-text-secondary max-w-md mx-auto">
          Local AI is now ready to use. You can generate scripts, analyze videos,
          and more - all processed locally on your machine.
        </p>
      </div>

      <div className="bg-terminal-bg rounded-lg border border-terminal-border p-4 max-w-md mx-auto">
        <h4 className="font-medium text-text-primary mb-2">Next Steps:</h4>
        <ul className="text-sm text-text-muted space-y-1 text-left">
          <li className="flex items-start gap-2">
            <Check className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
            Use AI to generate narration scripts
          </li>
          <li className="flex items-start gap-2">
            <Check className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
            Analyze videos to auto-create segments
          </li>
          <li className="flex items-start gap-2">
            <Check className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
            Download more models in Settings
          </li>
        </ul>
      </div>

      <button onClick={onFinish} className="btn-primary">
        Start Creating
      </button>
    </div>
  );
}
