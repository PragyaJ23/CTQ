/** CTQ logo mark: rounded square with a heart + pulse line.
 *  variant "teal"  — teal square, white heart (for light backgrounds)
 *  variant "light" — white square, teal heart (for the dark hero background)
 */
export default function Logo({ variant = "teal" }) {
  const square = variant === "light" ? "#ffffff" : "#388087";
  const heart = variant === "light" ? "#388087" : "#ffffff";
  const pulse = variant === "light" ? "#ffffff" : "#388087";
  return (
    <svg className={`brand-logo ${variant}`} viewBox="0 0 48 48" aria-hidden="true">
      <rect x="2" y="2" width="44" height="44" rx="12" fill={square} />
      <path
        d="M24 36c-6.4-4.1-12-8.4-12-14.2C12 17.6 15.2 15 19 15c2.1 0 3.9 1 5 2.6 1.1-1.6 2.9-2.6 5-2.6 3.8 0 7 2.6 7 6.8C36 27.6 30.4 31.9 24 36Z"
        fill={heart}
        opacity="0.95"
      />
      <path d="M14.5 24.5h6l2.5-5 3.5 9 2.5-4h4.5" stroke={pulse} strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
