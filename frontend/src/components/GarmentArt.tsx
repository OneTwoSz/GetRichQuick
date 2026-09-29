// Fallback visual for passports without a product photo: a clean line-art
// tee on a soft tinted panel, so the hero never looks empty.
export default function GarmentArt({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center bg-primary-50 ${className}`} aria-hidden>
      <svg viewBox="0 0 120 120" className="h-3/5 w-3/5 text-primary-600" fill="none" stroke="currentColor"
        strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round">
        <path
          d="M44 18 Q60 30 76 18 L100 30 L110 52 L92 60 L92 104 H28 L28 60 L10 52 L20 30 Z"
          fill="rgb(var(--primary-100))"
        />
        <path d="M44 18 Q60 30 76 18" />
        <path d="M28 60 L28 46 M92 60 L92 46" opacity="0.5" />
      </svg>
    </div>
  );
}
