import Link from "next/link";

export function BrandMark({
  className = "size-9",
}: {
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={`grid place-items-center overflow-hidden rounded-[10px] bg-brand text-white ${className}`}
    >
      <svg
        fill="none"
        role="img"
        viewBox="0 0 40 40"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M11.5 10.5V29.5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="3.2"
        />
        <path
          d="M19 10.5V27.5C19 28.6 19.9 29.5 21 29.5H29"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3.2"
        />
        <path
          d="M24.5 10.5H28.8V14.8"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2.6"
        />
      </svg>
    </span>
  );
}

export function Brand({ href = "/" }: { href?: string }) {
  return (
    <Link
      aria-label="ImmoLib — Accueil"
      className="inline-flex items-center gap-2.5"
      href={href}
    >
      <BrandMark />
      <span>
        <span className="block text-lg font-semibold tracking-[-0.045em] text-ink">
          ImmoLib
        </span>
      </span>
    </Link>
  );
}
