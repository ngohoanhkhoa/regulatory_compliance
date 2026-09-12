import { Loader2 } from "lucide-react";

export default function Button({
  children,
  variant = "primary",
  size = "md",
  isLoading = false,
  disabled = false,
  icon: Icon,
  className = "",
  ...props
}) {
  const base =
    "inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)] focus-visible:ring-[var(--accent)]";

  const variants = {
    primary:
      "bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] active:scale-[0.98] shadow-sm",
    secondary:
      "bg-[var(--surface2)] text-[var(--text)] border border-[var(--border)] hover:bg-[var(--surface3)] active:scale-[0.98]",
    ghost:
      "bg-transparent text-[var(--text-dim)] hover:text-[var(--text)] hover:bg-[var(--surface2)]",
    danger:
      "bg-[var(--bad)] text-white hover:opacity-90 active:scale-[0.98]",
  };

  const sizes = {
    sm: "px-3 py-1.5 text-sm",
    md: "px-4 py-2.5 text-sm",
    lg: "px-6 py-3 text-base",
    icon: "p-2",
  };

  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${
        disabled || isLoading ? "opacity-50 cursor-not-allowed active:scale-100" : ""
      } ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
      {!isLoading && Icon && <Icon className="w-4 h-4" />}
      {children}
    </button>
  );
}
