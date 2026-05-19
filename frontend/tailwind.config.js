/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Cormorant Garamond"', 'serif'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui'],
      },
      colors: {
        equine: {
          // Foundation surfaces (warm charcoal, subtle saddle undertone)
          black: '#13110E',
          soft: '#1C1814',
          card: '#22201C',
          elevated: '#2A2620',
          tertiary: '#322D26',
          hairline: '#332E26',
          graphite: '#4A423A',

          // Neutrals (warm, not cool)
          taupe: '#8A7E6C',
          platinum: '#C9C0AE',
          silver: '#D9D2C0',
          cream: '#EDE7D7',
          ivory: '#F5F2EC',

          // Equestrian accents
          saddle: '#8B6F4E',        // saddle leather
          saddleDeep: '#6B5640',
          brass: '#B89968',         // warm brass
          brassLight: '#D4B884',
          champagne: '#C9B690',     // warmer champagne

          // Accents (subtle steel for cool contrast)
          steel: '#5E7080',

          // Status (warmer, more refined)
          sage: '#7B9682',
          amber: '#C6924B',
          clay: '#A85C4B',
          slate: '#7A8390',
        },
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
        popover: { DEFAULT: 'hsl(var(--popover))', foreground: 'hsl(var(--popover-foreground))' },
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary: { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      keyframes: {
        'accordion-down': { from: { height: '0' }, to: { height: 'var(--radix-accordion-content-height)' } },
        'accordion-up': { from: { height: 'var(--radix-accordion-content-height)' }, to: { height: '0' } },
        'fade-in': { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'fade-in': 'fade-in 0.5s ease-out both',
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
