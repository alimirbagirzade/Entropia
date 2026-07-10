import { Link } from "react-router-dom";

// Add Outsource Signal (Stage 3 doc 03): the external-work TYPE CHOOSER — the
// single canonical entry surface for the two external Mainboard Working Item
// kinds. This surface performs NO backend call (doc 03 §7.1:
// start_transient_outsource_draft is transient UI state only — no root, no
// revision, no audit). Every field contract and save/import flow is owned by
// the child pages (docs 04/05, live since PR #119): choosing a type routes to
// the matching workbench, whose compose editor IS the transient draft.
// Persistence begins only at the child page's explicit Save (ID-03-01). The
// V18 hover submenu maps to this dedicated chooser page in the SPA nav
// skeleton (ID-03-04); direct choice links make a "continue without a choice"
// state unconstructible, so AOS-02 holds by construction. item_kind never
// extends PackageKind (CR-01): only trading_signal and trade_log exist here.
export function OutsourceSignal() {
  return (
    <>
      <h1 className="page-title">Add Outsource Signal</h1>
      <p className="page-sub">
        External working-object type chooser · the single canonical entry for Trading Signal and
        Trade Log
      </p>

      <section className="card" aria-labelledby="chooser-h">
        <h3 id="chooser-h" style={{ marginTop: 0 }}>
          Choose the external object type
        </h3>
        <p style={{ marginTop: 0, color: "var(--text-dim)" }}>
          Choose what the external source represents. Trading Signal is an actionable external
          event stream; Trade Log is completed historical trade data.
        </p>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 12 }}>
          <li>
            <TypeChoice
              to="/trading-signal"
              label="Trading Signal"
              helper={
                "Create a Trading Signal draft from an external signal source. The draft must " +
                "define time-safe event availability before it can be used in a backtest."
              }
            />
          </li>
          <li>
            <TypeChoice
              to="/trade-log"
              label="Trade Log"
              helper={
                "Create a Trade Log draft from imported historical trades. Import and validation " +
                "must complete before the log can be attached as a usable Mainboard item."
              }
            />
          </li>
        </ul>
        <p style={{ marginBottom: 0, color: "var(--text-dim)" }}>
          This source is an external working object, not a Package Library package.
        </p>
      </section>

      <section className="card" aria-labelledby="info-h">
        <h3 id="info-h" style={{ marginTop: 0 }}>
          About this surface
        </h3>
        <InfoPanel
          title="Add Outsource Signal"
          paragraphs={[
            "Buradan Package Libraryye yeni bir package eklemezsiniz. Dış kaynaklı bir çalışma nesnesi başlatırsınız.",
            "Trading Signal: Dış sağlayıcıdan gelen yönlü veya olay tabanlı sinyal akışıdır. Backtest yalnız her eventin gerçekten kullanılabilir hale geldiği available time sonrasında bu sinyali değerlendirebilir.",
            "Trade Log: Daha önce gerçekleşmiş işlem kayıtlarının dış kaynaktan içeri alınmış halidir. Canlı sinyal üretmez; geçmiş trade akışını analiz, kıyaslama veya araştırma bağlamında kullanır.",
            "Seçimi yaptıktan sonra açılan taslak, kaydedilene kadar Ready Check veya RUNa dahil edilmez.",
          ]}
        />
        <InfoPanel
          title="Trading Signal mi, Trade Log mu?"
          paragraphs={[
            "Trading Signal seçin: Kaynağınız zaman içinde gelen long/short veya olay bazlı signal eventleri sağlıyorsa. Her event için event time ile available time ayrımı korunmalıdır.",
            "Trade Log seçin: Kaynağınız gerçekleşmiş entry/exit kayıtlarını sağlıyorsa. Trade Log bir geçmiş kayıt nesnesidir; sistem bunu otomatik olarak yeni işlem açan canlı signal gibi yorumlamaz.",
            "Bir taslağın türünü sonradan değiştirmek yerine diğer türde yeni bir taslak başlatın. İki türün root, revision ve validation sözleşmeleri farklıdır.",
          ]}
        />
        <InfoPanel
          title="Unsaved External Draft"
          paragraphs={[
            "Bu satır yalnız geçici düzenleme stateidir. Henüz canonical Trading Signal veya Trade Log rootu, immutable revisionı ya da Mainboarda pinlenmiş itemi yoktur.",
            "Kaydetmeden bu taslak Ready Checke, Portfolio Allocationa veya RUN manifestine dahil edilmez. Taslağı kapatmak veya silmek Trash kaydı üretmez.",
            "Kalıcı hale getirmek için ilgili detay ekranındaki Save Draft veya Save and Attach işlemini tamamlayın.",
          ]}
        />
      </section>

      <section className="card" aria-labelledby="boundary-h">
        <h3 id="boundary-h" style={{ marginTop: 0 }}>
          What this surface does not do
        </h3>
        <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7 }}>
          <li>
            Choosing a type sends no request and creates no root, revision, audit event or Trash
            entry — leaving this page discards nothing durable.
          </li>
          <li>
            Saving, importing and revising happen on the child workbenches; a draft enters Ready
            Check, Portfolio Allocation or RUN only after its explicit Save there.
          </li>
          <li>
            Attach, pin and delete of persisted objects are Mainboard composition operations, not
            chooser actions.
          </li>
        </ul>
      </section>
    </>
  );
}

// One canonical choice row: a navigation link to the owning workbench plus the
// doc 03 §6.2 per-choice helper. A link (not a button) because the choice is
// pure navigation — the transient draft lives on the child page.
function TypeChoice({ to, label, helper }: { to: string; label: string; helper: string }) {
  return (
    <div style={{ border: "1px solid var(--border, #444)", borderRadius: 8, padding: 12 }}>
      <Link to={to} style={{ fontWeight: 600, fontSize: 16 }}>
        {label}
      </Link>
      <p style={{ margin: "6px 0 0", color: "var(--text-dim)" }}>{helper}</p>
    </div>
  );
}

// Doc 03 §6.1 ⓘ catalog, rendered verbatim (final UI text). Native
// <details>/<summary> keeps the panels keyboard-accessible without ARIA.
function InfoPanel({ title, paragraphs }: { title: string; paragraphs: string[] }) {
  return (
    <details style={{ marginBottom: 8 }}>
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>ⓘ {title}</summary>
      {paragraphs.map((text) => (
        <p key={text} style={{ margin: "8px 0 0", color: "var(--text-dim)" }}>
          {text}
        </p>
      ))}
    </details>
  );
}
