import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

// Tokens no formato do shadcn/ui (variáveis CSS em src/index.css).
const hsl = (v: string) => `hsl(var(--${v}) / <alpha-value>)`;

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "Segoe UI", "sans-serif"] },
      colors: {
        border: hsl("border"),
        input: hsl("input"),
        ring: hsl("ring"),
        background: hsl("background"),
        foreground: hsl("foreground"),
        muted: { DEFAULT: hsl("muted"), foreground: hsl("muted-foreground") },
        primary: { DEFAULT: hsl("primary"), foreground: hsl("primary-foreground") },
        secondary: { DEFAULT: hsl("secondary"), foreground: hsl("secondary-foreground") },
        accent: { DEFAULT: hsl("accent"), foreground: hsl("accent-foreground") },
        destructive: { DEFAULT: hsl("destructive"), foreground: hsl("destructive-foreground") },
        warning: { DEFAULT: hsl("warning"), foreground: hsl("warning-foreground") },
        card: { DEFAULT: hsl("card"), foreground: hsl("card-foreground") },
        attr: { elite: hsl("attr-elite"), good: hsl("attr-good"), mid: hsl("attr-mid"), low: hsl("attr-low") },
        pitch: { DEFAULT: hsl("pitch"), line: hsl("pitch-line") },
        chart: { 1: hsl("chart-1"), 2: hsl("chart-2"), 3: hsl("chart-3"), 4: hsl("chart-4"), ref: hsl("chart-ref") },
      },
      borderRadius: { lg: "var(--radius)", md: "calc(var(--radius) - 2px)", sm: "calc(var(--radius) - 4px)" },
    },
  },
  plugins: [animate],
} satisfies Config;
