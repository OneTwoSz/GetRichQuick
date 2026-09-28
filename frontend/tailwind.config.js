/** @type {import('tailwindcss').Config} */

// Every palette colour resolves to a CSS variable (defined in index.css for
// light and dark), so existing classes like bg-white / text-gray-600 /
// bg-red-50 re-theme automatically when <html> gets the `dark` class.
const scale = (name, stops = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]) =>
  Object.fromEntries(stops.map((s) => [s, `rgb(var(--${name}-${s}) / <alpha-value>)`]));

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // "white" is the card surface: white in light mode, graphite in dark.
        white: 'rgb(var(--white) / <alpha-value>)',
        gray: scale('gray'),
        primary: { DEFAULT: 'rgb(var(--primary-500) / <alpha-value>)', ...scale('primary') },
        accent: { DEFAULT: 'rgb(var(--accent) / <alpha-value>)' },
        green: scale('green'),
        red: scale('red'),
        amber: scale('amber'),
        yellow: scale('yellow'),
        blue: scale('blue'),
        teal: scale('teal'),
      },
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      boxShadow: {
        // Hairline ring + soft lift: reads as a crisp card edge in both themes.
        sm: '0 0 0 1px rgb(var(--hairline) / 1)',
        DEFAULT: '0 0 0 1px rgb(var(--hairline) / 1), 0 1px 2px rgb(var(--shadow) / 0.06)',
        md: '0 0 0 1px rgb(var(--hairline) / 1), 0 4px 12px -2px rgb(var(--shadow) / 0.10)',
        lg: '0 0 0 1px rgb(var(--hairline) / 1), 0 12px 32px -8px rgb(var(--shadow) / 0.18)',
      },
      borderRadius: {
        lg: '0.625rem',
        xl: '0.875rem',
      },
    },
  },
  plugins: [],
};
