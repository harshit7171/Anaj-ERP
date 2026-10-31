import type { ReactNode } from "react";

function Card({
  children,
  className = "",
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <section className={`retro-card ${className}`}>
      {title && <header className="retro-card-header">{title}</header>}
      <div className="retro-card-body">{children}</div>
    </section>
  );
}

export default Card;
