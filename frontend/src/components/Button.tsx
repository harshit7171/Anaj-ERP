import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "save" | "print" | "alert";

const variants: Record<Variant, string> = {
  primary:
    "bg-[#397f98] text-white border-[#284f60] hover:bg-[#284f60]",
  secondary:
    "bg-[#f8fafc] text-[#17252b] border-[#cbd5e1] hover:bg-[#e2e8f0]",
  ghost: "bg-transparent text-[#17252b] border-transparent hover:bg-[#e2e8f0]",
  danger: "btn-tactile-danger bg-[#dc2626] text-white border-[#991b1b]",
  save: "btn-tactile-save bg-[#16a34a] text-white border-[#1b5e20]",
  print: "btn-tactile-print bg-[#2563eb] text-white border-[#1e40af]",
  alert: "btn-tactile-alert bg-[#d97706] text-white border-[#92400e]",
};

function Button({
  children,
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  variant?: Variant;
}) {
  const tactile = variant === "save" || variant === "danger" || variant === "print" || variant === "alert";
  return (
    <button
      type="button"
      className={`btn-tactile inline-flex items-center justify-center gap-1 border px-3 py-1.5 text-xs font-semibold transition-all duration-100 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
      style={tactile ? undefined : { borderWidth: "2px", borderStyle: "outset" }}
      {...props}
    >
      {children}
    </button>
  );
}

export default Button;
