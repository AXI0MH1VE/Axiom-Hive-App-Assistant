/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        verity: {
          primary: '#2563eb',
          secondary: '#64748b',
          success: '#10b981',
          warning: '#f59e0b',
          danger: '#ef4444',
          neutral: '#f8fafc',
        },
      },
    },
  },
  plugins: [],
};
