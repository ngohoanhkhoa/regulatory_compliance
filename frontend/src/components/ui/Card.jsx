export default function Card({ children, className = "", padding = "md" }) {
  const paddings = { sm: "p-4", md: "p-5", lg: "p-6" };
  return (
    <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-sm ${paddings[padding]} ${className}`}>
      {children}
    </div>
  );
}
