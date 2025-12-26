/**
 * AI Provider configuration constants
 */

export type AIProviderType = 'ollama' | 'openai' | 'anthropic' | 'azure_openai' | 'google' | 'aws_bedrock' | 'huggingface' | 'custom'

export interface AIProviderModel {
  id: string
  name: string
}

export interface AIProviderConfig {
  name: string
  description: string
  requiresApiKey: boolean
  models: AIProviderModel[]
}

export const AI_PROVIDER_CONFIG: Record<AIProviderType, AIProviderConfig> = {
  ollama: {
    name: 'Ollama',
    description: 'Local AI',
    requiresApiKey: false,
    models: [], // Dynamic from Ollama
  },
  openai: {
    name: 'OpenAI',
    description: 'GPT-4',
    requiresApiKey: true,
    models: [
      { id: 'gpt-4o', name: 'GPT-4o' },
      { id: 'gpt-4-turbo-preview', name: 'GPT-4 Turbo' },
      { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo' },
    ],
  },
  anthropic: {
    name: 'Anthropic',
    description: 'Claude',
    requiresApiKey: true,
    models: [
      { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet' },
      { id: 'claude-3-opus-20240229', name: 'Claude 3 Opus' },
      { id: 'claude-3-haiku-20240307', name: 'Claude 3 Haiku' },
    ],
  },
  azure_openai: {
    name: 'Azure',
    description: 'Enterprise',
    requiresApiKey: true,
    models: [
      { id: 'gpt-4o', name: 'GPT-4o' },
      { id: 'gpt-35-turbo', name: 'GPT-3.5 Turbo' },
    ],
  },
  google: {
    name: 'Google',
    description: 'Gemini',
    requiresApiKey: true,
    models: [
      { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro' },
      { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash' },
    ],
  },
  aws_bedrock: {
    name: 'AWS',
    description: 'Bedrock',
    requiresApiKey: true,
    models: [
      { id: 'anthropic.claude-3-5-sonnet-20241022-v2:0', name: 'Claude 3.5' },
      { id: 'meta.llama3-70b-instruct-v1:0', name: 'Llama 3 70B' },
    ],
  },
  huggingface: {
    name: 'HuggingFace',
    description: 'Open',
    requiresApiKey: true,
    models: [
      { id: 'meta-llama/Llama-3.1-70B-Instruct', name: 'Llama 3.1 70B' },
      { id: 'mistralai/Mixtral-8x7B-Instruct-v0.1', name: 'Mixtral 8x7B' },
    ],
  },
  custom: {
    name: 'Custom',
    description: 'API',
    requiresApiKey: false,
    models: [{ id: 'default', name: 'Default' }],
  },
}

// Helper to get all provider types
export const AI_PROVIDER_TYPES: AIProviderType[] = [
  'ollama',
  'openai',
  'anthropic',
  'azure_openai',
  'google',
  'aws_bedrock',
  'huggingface',
  'custom',
]
