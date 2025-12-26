/**
 * Language constants for TTS and subtitle features
 */

export interface Language {
  code: string
  name: string
}

// All supported languages from edge-tts
export const LANGUAGES: Language[] = [
  { code: 'af', name: 'Afrikaans' },
  { code: 'am', name: 'Amharic' },
  { code: 'ar', name: 'Arabic' },
  { code: 'az', name: 'Azerbaijani' },
  { code: 'bg', name: 'Bulgarian' },
  { code: 'bn', name: 'Bengali' },
  { code: 'bs', name: 'Bosnian' },
  { code: 'ca', name: 'Catalan' },
  { code: 'cs', name: 'Czech' },
  { code: 'cy', name: 'Welsh' },
  { code: 'da', name: 'Danish' },
  { code: 'de', name: 'German' },
  { code: 'el', name: 'Greek' },
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Spanish' },
  { code: 'et', name: 'Estonian' },
  { code: 'fa', name: 'Persian' },
  { code: 'fi', name: 'Finnish' },
  { code: 'fil', name: 'Filipino' },
  { code: 'fr', name: 'French' },
  { code: 'ga', name: 'Irish' },
  { code: 'gl', name: 'Galician' },
  { code: 'gu', name: 'Gujarati' },
  { code: 'he', name: 'Hebrew' },
  { code: 'hi', name: 'Hindi' },
  { code: 'hr', name: 'Croatian' },
  { code: 'hu', name: 'Hungarian' },
  { code: 'id', name: 'Indonesian' },
  { code: 'is', name: 'Icelandic' },
  { code: 'it', name: 'Italian' },
  { code: 'iu', name: 'Inuktitut' },
  { code: 'ja', name: 'Japanese' },
  { code: 'jv', name: 'Javanese' },
  { code: 'ka', name: 'Georgian' },
  { code: 'kk', name: 'Kazakh' },
  { code: 'km', name: 'Khmer' },
  { code: 'kn', name: 'Kannada' },
  { code: 'ko', name: 'Korean' },
  { code: 'lo', name: 'Lao' },
  { code: 'lt', name: 'Lithuanian' },
  { code: 'lv', name: 'Latvian' },
  { code: 'mk', name: 'Macedonian' },
  { code: 'ml', name: 'Malayalam' },
  { code: 'mn', name: 'Mongolian' },
  { code: 'mr', name: 'Marathi' },
  { code: 'ms', name: 'Malay' },
  { code: 'mt', name: 'Maltese' },
  { code: 'my', name: 'Myanmar' },
  { code: 'nb', name: 'Norwegian' },
  { code: 'ne', name: 'Nepali' },
  { code: 'nl', name: 'Dutch' },
  { code: 'pl', name: 'Polish' },
  { code: 'ps', name: 'Pashto' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'ro', name: 'Romanian' },
  { code: 'ru', name: 'Russian' },
  { code: 'si', name: 'Sinhala' },
  { code: 'sk', name: 'Slovak' },
  { code: 'sl', name: 'Slovenian' },
  { code: 'so', name: 'Somali' },
  { code: 'sq', name: 'Albanian' },
  { code: 'sr', name: 'Serbian' },
  { code: 'su', name: 'Sundanese' },
  { code: 'sv', name: 'Swedish' },
  { code: 'sw', name: 'Swahili' },
  { code: 'ta', name: 'Tamil' },
  { code: 'te', name: 'Telugu' },
  { code: 'th', name: 'Thai' },
  { code: 'tr', name: 'Turkish' },
  { code: 'uk', name: 'Ukrainian' },
  { code: 'ur', name: 'Urdu' },
  { code: 'uz', name: 'Uzbek' },
  { code: 'vi', name: 'Vietnamese' },
  { code: 'zh', name: 'Chinese' },
  { code: 'zu', name: 'Zulu' },
]

// Sample text for different languages/scripts to preview fonts properly
export const LANGUAGE_SAMPLE_TEXT: Record<string, string> = {
  en: 'The quick brown fox jumps',
  ta: 'தமிழ் மொழி அழகானது',  // Tamil: "Tamil language is beautiful"
  hi: 'हिंदी भाषा सुंदर है',  // Hindi: "Hindi language is beautiful"
  te: 'తెలుగు భాష అందమైనది',  // Telugu
  kn: 'ಕನ್ನಡ ಭಾಷೆ ಸುಂದರ',  // Kannada
  ml: 'മലയാളം ഭാഷ മനോഹരം',  // Malayalam
  bn: 'বাংলা ভাষা সুন্দর',  // Bengali
  gu: 'ગુજરાતી ભાષા સુંદર છે',  // Gujarati
  mr: 'मराठी भाषा सुंदर आहे',  // Marathi
  pa: 'ਪੰਜਾਬੀ ਭਾਸ਼ਾ ਸੁੰਦਰ ਹੈ',  // Punjabi
  ur: 'اردو زبان خوبصورت ہے',  // Urdu
  ar: 'اللغة العربية جميلة',  // Arabic
  fa: 'زبان فارسی زیباست',  // Persian
  he: 'השפה העברית יפה',  // Hebrew
  zh: '中文字体预览示例',  // Chinese
  ja: '日本語フォントプレビュー',  // Japanese
  ko: '한국어 글꼴 미리보기',  // Korean
  th: 'ภาษาไทยสวยงาม',  // Thai
  vi: 'Tiếng Việt rất đẹp',  // Vietnamese
  ru: 'Русский язык красив',  // Russian
  el: 'Η ελληνική γλώσσα',  // Greek
  uk: 'Українська мова гарна',  // Ukrainian
  default: 'Sample subtitle text',
}

// Get sample text for a given language code
export function getSampleText(languageCode: string): string {
  return LANGUAGE_SAMPLE_TEXT[languageCode] || LANGUAGE_SAMPLE_TEXT.default
}

// Fallback fonts if API is not available
export const FALLBACK_FONTS = [
  'Roboto',
  'Open Sans',
  'Lato',
  'Montserrat',
  'Poppins',
  'Oswald',
  'Source Sans Pro',
  'Raleway',
  'Ubuntu',
  'Nunito',
  'Merriweather',
  'PT Sans',
  'Noto Sans',
  'Bebas Neue',
  'Anton',
  'Playfair Display',
]
