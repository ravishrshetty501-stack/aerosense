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
        // Hybrid Design System Tokens: Atlas Explorer × Air Intelligence Observatory × Atmosphere 360
        atlas: {
          bg: '#F5F7F5',
          surface: '#FFFFFF',
          subtle: '#EEF2EF',
          border: '#DCE5E0',
          text: '#172522',
          muted: '#687771',
          accent: '#087F73',
          secondary: '#256D83',
          success: '#16865C',
          warning: '#C17A19',
          danger: '#C64747',
        },
        darkAtlas: {
          bg: '#101714',
          surface: '#17211D',
          subtle: '#202D27',
          border: '#2B3A33',
          text: '#EDF4EF',
          muted: '#A4B4AA',
          accent: '#42B8A4',
          secondary: '#69A9B4',
          success: '#4BBF87',
          warning: '#E6AC54',
          danger: '#E46D6D',
        },
        // Backward compatibility mappings
        clima: {
          bg: '#F5F7F5',
          surface: '#FFFFFF',
          subtle: '#EEF2EF',
          border: '#DCE5E0',
          text: '#172522',
          muted: '#687771',
          accent: '#087F73',
          secondary: '#256D83',
        },
        darkClima: {
          bg: '#101714',
          surface: '#17211D',
          subtle: '#202D27',
          border: '#2B3A33',
          text: '#EDF4EF',
          muted: '#A4B4AA',
          accent: '#42B8A4',
          secondary: '#69A9B4',
        },
        navy: {
          950: '#101714',
          900: '#17211D',
          850: '#202D27',
          800: '#263830',
          700: '#2B3A33',
        },
        cyanAccent: {
          DEFAULT: '#087F73',
          dim: '#256D83',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        'sm-control': '6px',
        'std-panel': '10px',
        'lg-map': '12px',
      },
      boxShadow: {
        'subtle': '0 1px 3px 0 rgba(23, 37, 34, 0.04), 0 1px 2px -1px rgba(23, 37, 34, 0.04)',
        'floating': '0 4px 16px -2px rgba(23, 37, 34, 0.06), 0 2px 4px -1px rgba(23, 37, 34, 0.03)',
        'floating-dark': '0 4px 20px -2px rgba(0, 0, 0, 0.4), 0 2px 6px -1px rgba(0, 0, 0, 0.25)',
      }
    },
  },
  plugins: [],
}
