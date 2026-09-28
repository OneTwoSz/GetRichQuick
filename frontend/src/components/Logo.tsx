// GreenThread mark: a thread looping through a leaf-shaped eye.
export default function Logo({ withWordmark = true }: { withWordmark?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-white">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M5 19c0-8 6-14 14-14 0 8-6 14-14 14Z" />
          <path d="M5 19c3-3 6.5-6.5 10-10" />
        </svg>
      </span>
      {withWordmark && (
        <span className="text-[17px] font-semibold tracking-tight text-gray-900">
          Green<span className="text-primary">Thread</span>
        </span>
      )}
    </span>
  );
}
