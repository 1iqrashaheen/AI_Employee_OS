import { Priority } from "@/lib/types";

export default function PriorityBadge({ priority, suspicious }: { priority?: Priority; suspicious?: boolean }) {
  if (!priority) return <span className="badge badge-none">Not analyzed</span>;
  return (
    <span className="badges">
      <span className={`badge badge-${priority.toLowerCase()}`}>{priority}</span>
      {suspicious && <span className="badge badge-suspicious">Suspicious</span>}
    </span>
  );
}
