import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // GeoSentinel brand
        bg: {
          deep: '#0A1628',
          panel: '#0F1F36',
          card: '#152A47',
          line: '#1F3A5F',
        },
        brand: {
          primary: '#3B82F6',
          accent: '#22D3EE',
        },
        // Severity palette (Section 10.1)
        sev: {
          info: '#3B82F6',
          warning: '#F59E0B',
          critical: '#EF4444',
          evacuation: '#7C3AED',
        },
        // Status palette
        status: {
          good: '#10B981',
          caution: '#F59E0B',
          alert: '#EF4444',
          critical: '#EF4444',
          offline: '#6B7280',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-alarm': 'pulse 0.8s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
};

export default config;
