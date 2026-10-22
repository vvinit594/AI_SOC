import { Info } from "lucide-react";

export function MockBanner({ children }: { children: React.ReactNode }) {
  return (
    <div
      role="status"
      className="mb-6 flex gap-2 rounded-lg border border-cyan-500/20 bg-cyan-500/8 px-3 py-2 text-sm text-cyan-100"
    >
      <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p>{children}</p>
    </div>
  );
}
