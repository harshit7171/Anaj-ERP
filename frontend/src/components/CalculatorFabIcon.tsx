/** Green circular calculator launcher icon (SVG, no raster image). */
export default function CalculatorFabIcon() {
  const green = "#70D47B";
  const greenShadow = "#57B864";

  return (
    <svg aria-hidden className="calc-fab-icon" viewBox="0 0 64 64">
      <circle cx="32" cy="32" fill={green} r="32" />
      <path
        d="M34 38 L64 64 L64 36 Z"
        fill={greenShadow}
        opacity="0.85"
      />
      <rect fill="#fff" height="38" rx="3.5" width="32" x="16" y="12" />
      <rect fill={green} height="7" rx="1.2" width="26" x="19" y="16" />
      {[0, 1, 2].map((row) =>
        [0, 1, 2].map((col) => (
          <rect
            key={`${row}-${col}`}
            fill={green}
            height="5.5"
            rx="0.8"
            width="5.5"
            x={19 + col * 7.5}
            y={26 + row * 7.5}
          />
        )),
      )}
      {[0, 1, 2].map((row) => (
        <rect
          key={`r-${row}`}
          fill={green}
          height="5.5"
          rx="0.8"
          width="5.5"
          x={41.5}
          y={26 + row * 7.5}
        />
      ))}
      <rect fill={green} height="13" rx="0.8" width="5.5" x={41.5} y={41} />
    </svg>
  );
}
