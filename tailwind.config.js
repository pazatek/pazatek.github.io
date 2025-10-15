/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./*.html",
    "./script.js"
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Hanken Grotesk"', 'sans-serif'],
      },
    },
  },
  plugins: [],
} 