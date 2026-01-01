/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Console-inspired dark theme with red accents (for editor)
        terminal: {
          bg: '#0a0a0a',
          surface: '#121212',
          elevated: '#1a1a1a',
          border: '#2a2a2a',
          'border-hover': '#3a3a3a',
        },
        accent: {
          red: '#dc2626',
          'red-dark': '#b91c1c',
          'red-light': '#ef4444',
          'red-glow': '#dc262680',
          // Cyan/Blue theme for auth pages (matching website)
          cyan: '#06b6d4',
          'cyan-dark': '#0891b2',
          'cyan-light': '#22d3ee',
          'cyan-glow': '#06b6d480',
          blue: '#2563eb',
          'blue-dark': '#1d4ed8',
        },
        text: {
          primary: '#ffffff',
          secondary: '#a1a1aa',
          muted: '#71717a',
          disabled: '#52525b',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Monaco', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow-red': '0 0 20px rgba(220, 38, 38, 0.3)',
        'glow-red-sm': '0 0 10px rgba(220, 38, 38, 0.2)',
        'inner-glow': 'inset 0 0 20px rgba(220, 38, 38, 0.1)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'blink': 'blink 1s step-end infinite',
        'scan': 'scan 2s linear infinite',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
      },
    },
  },
  plugins: [],
}
