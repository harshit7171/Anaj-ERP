type Status = "normal" | "approaching" | "exceeded";

const styles: Record<Status, string> = {
  normal: "bg-[#ddf8e2] text-[#14541f] border-[#398d49]",
  approaching: "bg-[#fff4b8] text-[#4d3e00] border-[#9a6500]",
  exceeded: "bg-[#ffe2dc] text-[#8c1111] border-[#b92a22]",
};

const labels: Record<Status, string> = {
  normal: "Normal",
  approaching: "Approaching Limit",
  exceeded: "Limit Exceeded",
};

function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={`inline-flex items-center border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${styles[status]}`}
    >
      {labels[status]}
    </span>
  );
}

export type { Status };
export default StatusBadge;
