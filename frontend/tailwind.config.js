/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#0D9488',
          50: '#E6F7F5',
          100: '#CCEFEC',
          200: '#99DFD8',
          300: '#66CFC5',
          400: '#33BFB1',
          500: '#0D9488',
          600: '#0A766D',
          700: '#085952',
          800: '#053B36',
          900: '#031E1B',
        },
      },
    },
  },
  plugins: [],
}
