import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

export const CALCULATOR_WINDOW = "__calculator__";

type AngleMode = "deg" | "rad";

function factorial(n: number): number {
  if (n < 0 || !Number.isInteger(n)) {
    throw new Error("Invalid factorial");
  }
  if (n > 170) throw new Error("Overflow");
  let result = 1;
  for (let i = 2; i <= n; i += 1) result *= i;
  return result;
}

function evaluateExpression(
  raw: string,
  angleMode: AngleMode,
  ans: number,
  invert: boolean,
): number {
  let expr = raw.trim();
  if (!expr) return ans;
  expr = expr
    .replace(/×/g, "*")
    .replace(/÷/g, "/")
    .replace(/π/g, "PI")
    .replace(/\^/g, "**")
    .replace(/\be\b/g, "E");
  expr = expr.replace(/Ans/g, String(ans));
  expr = expr.replace(/(\d+(?:\.\d+)?)!/g, (_, n) => String(factorial(Number(n))));

  const toRad = (x: number) => (angleMode === "deg" ? (x * Math.PI) / 180 : x);
  const fromRad = (x: number) => (angleMode === "deg" ? (x * 180) / Math.PI : x);

  const sinFn = invert
    ? (x: number) => fromRad(Math.asin(x))
    : (x: number) => Math.sin(toRad(x));
  const cosFn = invert
    ? (x: number) => fromRad(Math.acos(x))
    : (x: number) => Math.cos(toRad(x));
  const tanFn = invert
    ? (x: number) => fromRad(Math.atan(x))
    : (x: number) => Math.tan(toRad(x));

  const fnBody = `
    const sin = args.sin, cos = args.cos, tan = args.tan, log = Math.log10, ln = Math.log;
    const sqrt = Math.sqrt, PI = Math.PI, E = Math.E, exp = Math.exp;
    return (${expr});
  `;
  const args = {
    sin: sinFn,
    cos: cosFn,
    tan: tanFn,
    log: Math.log10,
    ln: Math.log,
    sqrt: Math.sqrt,
    PI: Math.PI,
    E: Math.E,
    exp: Math.exp,
  };
  // eslint-disable-next-line @typescript-eslint/no-implied-eval
  const compute = new Function("args", fnBody) as (a: typeof args) => number;
  const value = compute(args);
  if (!Number.isFinite(value)) {
    throw new Error("Invalid result");
  }
  return value;
}

type CalcButton = {
  label: string;
  className?: string;
  action: "append" | "clear" | "equals" | "mode" | "invert" | "percent" | "ans";
  value?: string;
};

const ROWS: CalcButton[][] = [
  [
    { label: "Deg", action: "mode", value: "deg" },
    { label: "Rad", action: "mode", value: "rad" },
    { label: "x!", action: "append", value: "!" },
    { label: "(", action: "append", value: "(" },
    { label: ")", action: "append", value: ")" },
    { label: "%", action: "percent" },
    { label: "AC", action: "clear", className: "calc-btn-muted" },
  ],
  [
    { label: "Inv", action: "invert", className: "calc-btn-muted" },
    { label: "sin", action: "append", value: "sin(" },
    { label: "ln", action: "append", value: "ln(" },
    { label: "7", action: "append", value: "7" },
    { label: "8", action: "append", value: "8" },
    { label: "9", action: "append", value: "9" },
    { label: "÷", action: "append", value: "÷" },
  ],
  [
    { label: "π", action: "append", value: "π" },
    { label: "cos", action: "append", value: "cos(" },
    { label: "log", action: "append", value: "log(" },
    { label: "4", action: "append", value: "4" },
    { label: "5", action: "append", value: "5" },
    { label: "6", action: "append", value: "6" },
    { label: "×", action: "append", value: "×" },
  ],
  [
    { label: "e", action: "append", value: "E" },
    { label: "tan", action: "append", value: "tan(" },
    { label: "√", action: "append", value: "sqrt(" },
    { label: "1", action: "append", value: "1" },
    { label: "2", action: "append", value: "2" },
    { label: "3", action: "append", value: "3" },
    { label: "-", action: "append", value: "-" },
  ],
  [
    { label: "Ans", action: "ans" },
    { label: "EXP", action: "append", value: "exp(" },
    { label: "xʸ", action: "append", value: "^" },
    { label: "0", action: "append", value: "0", className: "calc-btn-zero" },
    { label: ".", action: "append", value: "." },
    { label: "=", action: "equals", className: "calc-btn-equals" },
    { label: "+", action: "append", value: "+" },
  ],
];

export default function CalculatorPopup({
  open,
  onClose,
}: {
  open: boolean;
  onClose(): void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number } | null>(
    null,
  );

  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [initialized, setInitialized] = useState(false);
  const [angleMode, setAngleMode] = useState<AngleMode>("deg");
  const [invert, setInvert] = useState(false);
  const [expression, setExpression] = useState("");
  const [display, setDisplay] = useState("0");
  const [ans, setAns] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || initialized) return;
    const width = 320;
    const height = 420;
    setPosition({
      x: Math.max(16, window.innerWidth - width - 24),
      y: Math.max(72, window.innerHeight - height - 24),
    });
    setInitialized(true);
  }, [open, initialized]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const runEquals = useCallback(() => {
    try {
      setError("");
      const value = evaluateExpression(expression || display, angleMode, ans, invert);
      const text = String(value);
      setDisplay(text);
      setExpression(text);
      setAns(value);
    } catch {
      setError("Error");
    }
  }, [angleMode, ans, expression, display, invert]);

  function handleButton(button: CalcButton) {
    setError("");
    switch (button.action) {
      case "clear":
        setExpression("");
        setDisplay("0");
        return;
      case "mode":
        setAngleMode(button.value === "rad" ? "rad" : "deg");
        return;
      case "invert":
        setInvert((prev) => !prev);
        return;
      case "ans":
        setExpression((prev) => `${prev}Ans`);
        setDisplay(String(ans));
        return;
      case "percent": {
        const base = expression || display;
        try {
          const value = evaluateExpression(base, angleMode, ans, invert) / 100;
          const text = String(value);
          setDisplay(text);
          setExpression(text);
        } catch {
          setError("Error");
        }
        return;
      }
      case "equals":
        runEquals();
        return;
      case "append":
        if (button.value === undefined) return;
        setExpression((prev) => {
          const next = prev === "0" && /^\d$/.test(button.value!) ? button.value! : prev + button.value!;
          setDisplay(next || "0");
          return next;
        });
        return;
      default:
        return;
    }
  }

  function onHeaderPointerDown(event: ReactPointerEvent) {
    if (event.button !== 0) return;
    if ((event.target as HTMLElement).closest(".calc-popup-close")) return;
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: position.x,
      originY: position.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onHeaderPointerMove(event: ReactPointerEvent) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    setPosition({
      x: drag.originX + (event.clientX - drag.startX),
      y: drag.originY + (event.clientY - drag.startY),
    });
  }

  function onHeaderPointerUp(event: ReactPointerEvent) {
    if (dragRef.current?.pointerId === event.pointerId) {
      dragRef.current = null;
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  if (!open) return null;

  return (
    <div className="calc-popup-layer" role="presentation">
      <div
        ref={panelRef}
        className="calc-popup-panel"
        role="dialog"
        aria-label="Calculator"
        style={{ transform: `translate(${position.x}px, ${position.y}px)` }}
      >
        <header
          className="calc-popup-header"
          onPointerDown={onHeaderPointerDown}
          onPointerMove={onHeaderPointerMove}
          onPointerUp={onHeaderPointerUp}
        >
          <span aria-hidden="true" className="calc-popup-clock">
            🕒
          </span>
          <span className="calc-popup-drag-hint">Drag to move</span>
          <output className="calc-popup-display">{error || display}</output>
          <button
            aria-label="Close calculator"
            className="calc-popup-close"
            type="button"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => {
              event.stopPropagation();
              onClose();
            }}
          >
            ×
          </button>
        </header>
        <p className="calc-popup-mode">
          {angleMode === "deg" ? "DEG" : "RAD"}
          {invert ? " · INV" : ""}
          {expression && expression !== display ? ` · ${expression}` : ""}
        </p>
        <div className="calc-popup-grid">
          {ROWS.flatMap((row, rowIndex) =>
            row.map((button) => (
              <button
                key={`${rowIndex}-${button.label}`}
                className={`calc-popup-btn ${button.className ?? ""}${
                  (button.action === "mode" && button.value === angleMode) ||
                  (button.label === "Inv" && invert)
                    ? " calc-popup-btn-active"
                    : ""
                }`.trim()}
                type="button"
                onClick={() => handleButton(button)}
              >
                {button.label}
              </button>
            )),
          )}
        </div>
      </div>
    </div>
  );
}
