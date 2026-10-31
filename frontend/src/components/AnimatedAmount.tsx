import { useEffect, useRef, useState } from "react";

function AnimatedAmount({
  valuePaise,
  prefix = "₹",
}: {
  valuePaise: number;
  prefix?: string;
}) {
  const [display, setDisplay] = useState(valuePaise);
  const previous = useRef(valuePaise);
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (reducedMotion) {
      setDisplay(valuePaise);
      previous.current = valuePaise;
      return;
    }
    const start = previous.current;
    const delta = valuePaise - start;
    if (delta === 0) return;
    const started = performance.now();
    const duration = 220;
    let frame = 0;
    const tick = (now: number) => {
      const progress = Math.min((now - started) / duration, 1);
      setDisplay(Math.round(start + delta * progress));
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        previous.current = valuePaise;
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [valuePaise, reducedMotion]);

  return (
    <span className="tabular-money font-semibold text-[var(--color-accent)]">
      {prefix}{(display / 100).toFixed(2)}
    </span>
  );
}

export default AnimatedAmount;
