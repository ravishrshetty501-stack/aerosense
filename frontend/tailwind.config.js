/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#070b14',
          900: '#0b1329',
          850: '#0f1b38',
          800: '#14234b',
          700: '#1e3369',
          600: '#2a478f',
        },
        charcoal: {
          950: '#0a0d12',
          900: '#111620',
          850: '#171e2c',
          800: '#1e2738',
          700: '#2c374d',
        },
        surface: {
          base: '#0b1329',
          panel: '#111b36',
          card: '#162344',
          border: 'rgba(56, 189, 248, 0.12)',
          highlight: 'rgba(56, 189, 248, 0.06)',
        },
        cyanAccent: {
          DEFAULT: '#00f2fe',
          glow: 'rgba(0, 242, 254, 0.18)',
          dim: '#00b4d8',
        },
        aqi: {
          good: '#10b981',        // Green
          moderate: '#f59e0b',    // Amber / Yellow
          sensitive: '#f97316',   // Orange
          unhealthy: '#ef4444',   // Red
          veryUnhealthy: '#8b5cf6', // Purple
          hazardous: '#7f1d1d',   // Maroon
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
