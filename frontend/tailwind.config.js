/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        linkedin: {
          light: '#3b82f6',
          DEFAULT: '#0a66c2',
          dark: '#004182',
        }
      }
    },
  },
  plugins: [],
}
