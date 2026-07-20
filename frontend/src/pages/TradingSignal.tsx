import { TradingSignalEditor } from "@/components/TradingSignalEditor";

// Trading Signal page (Stage 3c, doc 04 §7–§9). R2-01a — this page is a thin
// wrapper: the whole two-column editor body now lives in
// components/TradingSignalEditor.tsx so R2-01b can mount the same editor inline
// on a Mainboard row. The page keeps only the v18 page chrome; the editor keeps
// the URL modes ?job= (durable import handle, CR-09) and ?root= (work-object
// detail + revision composer) in mode="page".
export function TradingSignal() {
  return (
    <>
      <h1 className="page-title">Trading Signal</h1>
      <p className="page-sub">
        Import external signal events from a TXT/CSV file, review the normalization report, and
        save the Trading Signal as a native work object on the Mainboard
      </p>

      <TradingSignalEditor mode="page" />
    </>
  );
}
