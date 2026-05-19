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
          /* ============ SURFACES (light) ============ */
          black:       '#F7F5FA',  // primary BG — soft lavender ivory
          soft:        '#EAE7F2',  // secondary surface — lavender mist
          card:        '#FDFBFF',  // elevated card — pearl white
          elevated:    '#FFFFFF',  // top elevation
          tertiary:    '#F0EDF5',
          hairline:    '#E0DCEC',
          graphite:    '#B8BDC9',  // brushed silver (borders, dividers)

          /* ============ TEXT (ink-style) ============ */
          ink:         '#2A2A32',  // primary text
          inkMuted:    '#666674',  // secondary text
          inkSoft:     '#9A98A8',  // muted text

          /* ============ Legacy text aliases ============ */
          ivory:       '#2A2A32',  // legacy: text-equine-ivory now = primary ink
          cream:       '#2E3448',
          silver:      '#666674',
          platinum:    '#9A98A8',

          /* ============ ACCENTS ============ */
          navy:        '#2E3448',  // deep charcoal navy (sidebar, primary brand)
          navyDeep:    '#22262F',
          navyLift:    '#3D445A',
          brass:       '#A7B7E7',  // icy blue (primary accent — was brass)
          brassLight:  '#C2CDEC',  // light icy blue
          saddle:      '#C7B6D9',  // dusty lavender (was saddle leather)
          saddleDeep:  '#A593C0',
          champagne:   '#B89B7A',  // muted champagne taupe (warm accent)
          taupe:       '#B8BDC9',  // brushed silver
          steel:       '#A7B7E7',  // icy blue (alias)

          /* ============ STATUS (muted, refined) ============ */
          sage:        '#7AA08A',  // soft sage (darker for contrast on light)
          amber:       '#B5894A',  // muted golden sand (darkened)
          clay:        '#8B5E6B',  // muted mauve
          slate:       '#666674',
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
