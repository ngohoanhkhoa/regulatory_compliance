import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

export default function Input({
  label,
  error,
  icon: Icon,
  type = "text",
  className = "",
  ...props
}) {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === "password";
  const inputType = isPassword ? (showPassword ? "text" : "password") : type;

  return (
    <div className={`w-full ${className}`}>
      {label && (
        <label className="block text-sm font-medium text-[var(--text-dim)] mb-1.5">
          {label}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <Icon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
        )}
        <input
          type={inputType}
          className={`w-full bg-[var(--surface2)] border border-[var(--border)] rounded-lg text-[var(--text)] placeholder:text-[var(--text-muted)] transition-all duration-200 focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-muted)] focus:outline-none ${
            Icon ? "pl-10" : "pl-3"
          } pr-${isPassword ? "10" : "3"} py-2.5`}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
      {error && <p className="mt-1 text-sm text-[var(--bad)]">{error}</p>}
    </div>
  );
}
