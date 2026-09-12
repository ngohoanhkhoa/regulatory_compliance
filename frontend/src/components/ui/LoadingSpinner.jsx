import { Loader2 } from "lucide-react";

export default function LoadingSpinner({ size = "md", text = "Loading…" }) {
  const sizes = { sm: "w-4 h-4", md: "w-6 h-6", lg: "w-8 h-8" };
  return (
    <div className="flex flex-col items-center gap-3 py-8">
      <Loader2 className={`${sizes[size]} text-[var(--accent)] animate-spin`} />
      {text && <span className="text-sm text-[var(--text-dim)]">{text}</span>}
    </div>
  );
}
