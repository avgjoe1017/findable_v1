import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Dark theme matching existing templates
        background: {
          DEFAULT: '#0a0f1a', // slate-950
          secondary: '#0f172a', // slate-900
          tertiary: '#1e293b', // slate-800
        },
        foreground: {
          DEFAULT: '#f1f5f9', // slate-100
          muted: '#94a3b8', // slate-400
          subtle: '#64748b', // slate-500
        },
        primary: {
          DEFAULT: '#14b8a6', // teal-500
          hover: '#0d9488', // teal-600
          light: '#2dd4bf', // teal-400
        },
        accent: {
          DEFAULT: '#6366f1', // indigo-500
          hover: '#4f46e5', // indigo-600
        },
        // Grade colors
        grade: {
          a: '#22d3ee', // cyan-400
          b: '#4ade80', // green-400
          c: '#fbbf24', // amber-400
          d: '#fb923c', // orange-400
          f: '#f87171', // red-400
        },
        // Border and card colors
        border: {
          DEFAULT: '#334155', // slate-700
          muted: '#1e293b', // slate-800
        },
        card: {
          DEFAULT: '#0f172a', // slate-900
          hover: '#1e293b', // slate-800
        },
      },
      fontFamily: {
        serif: ['Instrument Serif', 'Georgia', 'serif'],
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'score-ring': 'score-ring 1.5s ease-out forwards',
        'shimmer': 'shimmer 2s infinite',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
      },
      keyframes: {
        'score-ring': {
          '0%': { strokeDashoffset: '314' },
          '100%': { strokeDashoffset: 'var(--target-offset)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      backgroundImage: {
        'shimmer-gradient': 'linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)',
      },
    },
  },
  plugins: [],
}

export default config
