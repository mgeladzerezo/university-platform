import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Both pass WCAG AA (4.5:1) for white text and as text on white.
        brand: { DEFAULT: "#1d4e89", dark: "#143961" },
      },
    },
  },
  plugins: [],
};

export default config;
