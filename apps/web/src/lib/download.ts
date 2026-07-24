import type { RentalDocument } from "@/types/domain";

export function rentalDocumentPdfFilename(document: RentalDocument) {
  const prefix =
    document.document_type === "RENT_RECEIPT"
      ? "quittance"
      : document.document_type === "DEPOSIT_SETTLEMENT"
        ? "releve-caution"
        : "recu";
  return `${prefix}-${document.reference}.pdf`;
}

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}
