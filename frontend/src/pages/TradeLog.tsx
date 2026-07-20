import { TradeLogEditor } from "@/components/TradeLogEditor";

// Trade Log page (Stage 3d, doc 05 §8–§10). R2-01a — this page is a thin
// wrapper: the whole two-column editor body now lives in
// components/TradeLogEditor.tsx so R2-01b can mount the same editor inline on a
// Mainboard row. The page keeps only the v18 page chrome; the editor keeps the
// URL modes ?job= (durable import handle, CR-09) and ?root= (work-object detail
// + revision composer) in mode="page".
export function TradeLog() {
  return (
    <>
      <h1 className="page-title">Trade Log</h1>
      <p className="page-sub">
        Import a historical trade ledger from a TXT/CSV file, review the canonical record batch,
        and save the Trade Log as a native work object on the Mainboard
      </p>

      <TradeLogEditor mode="page" />
    </>
  );
}
