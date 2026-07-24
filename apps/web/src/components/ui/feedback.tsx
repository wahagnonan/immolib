import { CheckCircle2, CircleAlert } from "lucide-react";

export function Feedback({
  message,
  tone = "success",
}: {
  message: string | null;
  tone?: "success" | "error";
}) {
  if (!message) return null;
  const Icon = tone === "success" ? CheckCircle2 : CircleAlert;

  return (
    <div
      className={`flex items-start gap-3 rounded-[10px] border px-4 py-3 text-sm ${
        tone === "success"
          ? "border-[#dbeadf] bg-[#edf5ef] text-[#275c3b]"
          : "border-red-200 bg-red-50 text-red-700"
      }`}
      role={tone === "error" ? "alert" : "status"}
    >
      <Icon aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
      <span>{message}</span>
    </div>
  );
}
