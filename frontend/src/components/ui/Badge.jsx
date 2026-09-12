export default function Badge({ children, variant = "default", className = "" }) {
  const variants = {
    default: "bg-[var(--surface2)] text-[var(--text-dim)] border-[var(--border)]",
    success: "bg-[var(--good-muted)] text-[var(--good)] border-[var(--good)]/20",
    danger: "bg-[var(--bad-muted)] text-[var(--bad)] border-[var(--bad)]/20",
    warning: "bg-[var(--warn-muted)] text-[var(--warn)] border-[var(--warn)]/20",
    info: "bg-[var(--accent-muted)] text-[var(--accent)] border-[var(--accent)]/20",
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium rounded-full border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
}
