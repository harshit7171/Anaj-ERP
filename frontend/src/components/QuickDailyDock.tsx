function QuickDailyDock({ onOpen }: { onOpen(title: string): void }) {
  const items = [
    { label: "J Form (Parchi)", key: "J Form (Parchi)" },
    { label: "I Form (Auction Bill)", key: "I Form (Auction Bill)" },
    { label: "Gate Pass", key: "Gate Pass" },
    { label: "Lifting Entry", key: "Lifting Entry" },
  ];
  return (
    <nav aria-label="Daily mandi shortcuts" className="quick-daily-dock">
      {items.map((item) => (
        <button key={item.key} type="button" onClick={() => onOpen(item.key)}>
          {item.label}
        </button>
      ))}
    </nav>
  );
}

export default QuickDailyDock;
