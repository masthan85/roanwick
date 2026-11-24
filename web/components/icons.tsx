// One icon set: 20px, 1.75px stroke, currentColor. Decorative by default (aria-hidden); pair with visible or sr-only text.
type P = { className?: string; size?: number };
const base = (size = 20) => ({ width: size, height: size, viewBox: "0 0 20 20", fill: "none", stroke: "currentColor", strokeWidth: 1.75, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true });

export const CheckIcon = ({ className, size }: P) => (
  <svg {...base(size)} className={className}><path d="M4.5 10.5l3.5 3.5 7.5-8" /></svg>
);
export const CloseIcon = ({ className, size }: P) => (
  <svg {...base(size)} className={className}><path d="M5 5l10 10M15 5L5 15" /></svg>
);
export const ArrowIcon = ({ className, size }: P) => (
  <svg {...base(size)} className={className}><path d="M4 10h12M11 5l5 5-5 5" /></svg>
);
export const StarIcon = ({ className, size = 16, filled }: P & { filled?: boolean }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden className={className} fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={1.5} strokeLinejoin="round">
    <path d="M10 2.5l2.3 4.9 5.2.7-3.8 3.6 1 5.3L10 14.4l-4.7 2.6 1-5.3L2.5 8.1l5.2-.7L10 2.5z" />
  </svg>
);
