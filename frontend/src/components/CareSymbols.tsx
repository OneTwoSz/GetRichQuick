// Care-label symbols: vocabulary (mirrors backend utils/care_symbols.py),
// line-drawn icons, a read-only row for passports and a picker.

export const CARE_CATEGORIES = ['washing', 'bleaching', 'drying', 'ironing', 'professional'] as const;
export type CareCategory = (typeof CARE_CATEGORIES)[number];

export const CARE_SYMBOLS: Record<string, { category: CareCategory; label: string }> = {
  wash_30: { category: 'washing', label: 'Machine wash 30°C' },
  wash_30_gentle: { category: 'washing', label: 'Machine wash 30°C, gentle cycle' },
  wash_40: { category: 'washing', label: 'Machine wash 40°C' },
  wash_60: { category: 'washing', label: 'Machine wash 60°C' },
  hand_wash: { category: 'washing', label: 'Hand wash only' },
  do_not_wash: { category: 'washing', label: 'Do not wash' },
  bleach_any: { category: 'bleaching', label: 'Any bleach allowed' },
  bleach_non_chlorine: { category: 'bleaching', label: 'Non-chlorine bleach only' },
  do_not_bleach: { category: 'bleaching', label: 'Do not bleach' },
  tumble_low: { category: 'drying', label: 'Tumble dry, low heat' },
  tumble_normal: { category: 'drying', label: 'Tumble dry, normal heat' },
  do_not_tumble: { category: 'drying', label: 'Do not tumble dry' },
  line_dry: { category: 'drying', label: 'Line dry' },
  dry_flat: { category: 'drying', label: 'Dry flat' },
  iron_low: { category: 'ironing', label: 'Iron at low temperature (110°C)' },
  iron_medium: { category: 'ironing', label: 'Iron at medium temperature (150°C)' },
  iron_high: { category: 'ironing', label: 'Iron at high temperature (200°C)' },
  do_not_iron: { category: 'ironing', label: 'Do not iron' },
  dry_clean: { category: 'professional', label: 'Professional dry clean' },
  do_not_dry_clean: { category: 'professional', label: 'Do not dry clean' },
};

const CATEGORY_LABELS: Record<CareCategory, string> = {
  washing: 'Washing',
  bleaching: 'Bleaching',
  drying: 'Drying',
  ironing: 'Ironing',
  professional: 'Dry cleaning',
};

const Cross = () => <path d="M6 6 L34 34 M34 6 L6 34" />;
const Dots = ({ n, y, cx = 20 }: { n: number; y: number; cx?: number }) => (
  <>
    {Array.from({ length: n }, (_, i) => (
      <circle key={i} cx={cx + (i - (n - 1) / 2) * 5} cy={y} r="1.4" fill="currentColor" stroke="none" />
    ))}
  </>
);
const Tub = () => (
  <>
    <path d="M5 13 L9 32 H31 L35 13" />
    <path d="M5 13 q3.75 -3 7.5 0 t7.5 0 t7.5 0 t7.5 0" />
  </>
);

function glyph(code: string) {
  switch (code) {
    case 'wash_30':
    case 'wash_40':
    case 'wash_60':
    case 'wash_30_gentle':
      return (
        <>
          <Tub />
          <text x="20" y="27.5" textAnchor="middle" fontSize="9" fontWeight="600" fill="currentColor" stroke="none">
            {code.split('_')[1]}
          </text>
          {code === 'wash_30_gentle' && <path d="M9 36 H31" />}
        </>
      );
    case 'hand_wash':
      return (
        <>
          <Tub />
          <path d="M15 29 v-7 m3 7 v-9 m3 9 v-8 m3 8 v-6 M13 25 q1 4 4 5 h7" />
        </>
      );
    case 'do_not_wash':
      return (<><Tub /><Cross /></>);
    case 'bleach_any':
      return <path d="M20 6 L35 32 H5 Z" />;
    case 'bleach_non_chlorine':
      return (<><path d="M20 6 L35 32 H5 Z" /><path d="M17 16 L11 27 M23 16 L17 27" /></>);
    case 'do_not_bleach':
      return (<><path d="M20 6 L35 32 H5 Z" /><Cross /></>);
    case 'tumble_low':
    case 'tumble_normal':
      return (
        <>
          <rect x="6" y="6" width="28" height="28" />
          <circle cx="20" cy="20" r="10" />
          <Dots n={code === 'tumble_low' ? 1 : 2} y={20} />
        </>
      );
    case 'do_not_tumble':
      return (<><rect x="6" y="6" width="28" height="28" /><circle cx="20" cy="20" r="10" /><Cross /></>);
    case 'line_dry':
      return (<><rect x="6" y="6" width="28" height="28" /><path d="M6 12 q14 10 28 0" /></>);
    case 'dry_flat':
      return (<><rect x="6" y="6" width="28" height="28" /><path d="M12 20 H28" /></>);
    case 'iron_low':
    case 'iron_medium':
    case 'iron_high':
    case 'do_not_iron':
      return (
        <>
          <path d="M5 30 H34 L32 18 Q31 13 25 13 H14" />
          <path d="M10 13 H14 M5 30 Q7 20 15 18 H32" />
          {code === 'do_not_iron' ? <Cross /> : <Dots n={{ iron_low: 1, iron_medium: 2, iron_high: 3 }[code] ?? 1} y={24} cx={21} />}
        </>
      );
    case 'dry_clean':
      return (
        <>
          <circle cx="20" cy="20" r="14" />
          <text x="20" y="25" textAnchor="middle" fontSize="13" fontWeight="600" fill="currentColor" stroke="none">P</text>
        </>
      );
    case 'do_not_dry_clean':
      return (<><circle cx="20" cy="20" r="14" /><Cross /></>);
    default:
      return <circle cx="20" cy="20" r="14" />;
  }
}

export function CareIcon({ code, className = 'h-8 w-8' }: { code: string; className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" role="img" aria-label={CARE_SYMBOLS[code]?.label ?? code}>
      {glyph(code)}
    </svg>
  );
}

/** Read-only row of symbols with labels (passport page). */
export function CareSymbolRow({ codes }: { codes: string[] }) {
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {codes.map((code) => (
        <li key={code} className="flex flex-col items-center gap-2 rounded-lg bg-gray-50 p-3 text-center">
          <span className="text-gray-800"><CareIcon code={code} className="h-10 w-10" /></span>
          <span className="text-[11px] leading-snug text-gray-600">{CARE_SYMBOLS[code]?.label ?? code}</span>
        </li>
      ))}
    </ul>
  );
}

/** One-per-category picker. `value` is the list of selected codes. */
export function CareSymbolPicker({ value, onChange }: { value: string[]; onChange: (codes: string[]) => void }) {
  const selected = new Set(value);
  const toggle = (code: string) => {
    const category = CARE_SYMBOLS[code].category;
    const rest = value.filter((c) => CARE_SYMBOLS[c]?.category !== category);
    onChange(selected.has(code) ? rest : [...rest, code]);
  };
  return (
    <div className="space-y-3">
      {CARE_CATEGORIES.map((category) => (
        <div key={category}>
          <div className="mb-1.5 text-xs font-medium text-gray-500">{CATEGORY_LABELS[category]}</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(CARE_SYMBOLS)
              .filter(([, s]) => s.category === category)
              .map(([code, s]) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => toggle(code)}
                  title={s.label}
                  aria-pressed={selected.has(code)}
                  className={`flex h-12 w-12 items-center justify-center rounded-lg border transition-colors ${
                    selected.has(code)
                      ? 'border-primary bg-primary-50 text-primary-700'
                      : 'border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-800'
                  }`}
                >
                  <CareIcon code={code} className="h-7 w-7" />
                </button>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
