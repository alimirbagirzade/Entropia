# Stage 3d — Trade Log (doc 05) — Kickoff / Resume Handoff

> **Amaç:** Yeni/temiz bir oturumda kaldığımız yerden devam edebilmek için hazır bağlam + **yapıştırmaya hazır başlangıç prompt'u**. Bu dosya her kapanış oturumunda güncellenir (bir sonraki dilim için).

## Nerede kaldık (2026-07-01)

- **Stage 3a (Mainboard)** ✅ merged — PR #7, alembic 0008.
- **Stage 3b (Strategy Details)** ✅ merged — PR #9, alembic 0009.
- **Stage 3c (Trading Signal, doc 04 + Add Outsource Signal doc 03 Trading-Signal yolu)** ✅ merged — PR #10, **main = `49baed6`**, **alembic head = `0010_trading_signal`**.
- **Sıradaki = Stage 3d — Trade Log (doc 05).** Branch henüz yok (oturumda aç: `feat/stage-3d-trade-log`).

## Otorite sırası (önce oku)

1. `docs/STAGE2_HANDOFF.md` → "Stage 3c … ✅ landed" + "Next: Stage 3d" bölümleri, **working loop**, dersler **L1–L7**, reusable foundation.
2. `docs/STAGE_BUILD_PLAN.md` → Stage 3 tablosundaki **"Trade Log (05)"** satırı + Stage 3 acceptance.
3. `docs/spec/05_Entropia_V18_Trade_Log_Page_Documentation_v1_1.md` → spec'i TAM çıkar (özellikle field/import contract, command payloads, domain model §9, acceptance tests).
4. ecc memory graph → **"Entropia Stage 3c — Trading Signal"** checkpoint'i (3d tasarım pointer'ı orada).

## Tasarım yön verici (3c'den taşınan bilgi — doğrula + uygula)

- **Trade Log = external work object (`object_kind=trade_log`), historical trade data — canlı sinyal ÜRETMEZ.** Trading Signal event şeması (`event_time/available_time/direction/signal_type`) DEĞİL; Trade Log **entry/exit ledger** şemasıdır (`direction, entry_time, entry_price, exit_time, exit_price`).
- **Karar ver:** Trade Log da 3c gibi **native work object** mı olsun (root/revision = `work_object_root/revision`, mirror yok) yoksa ayrı `trade_log_root/revision` mi? 3c'de native seçildi ve çok temiz oldu — **büyük ihtimalle native tekrar** (doc 05 §9'u kontrol et). O zaman YENİ tablo sadece `canonical_trade_record_batch` (parse edilmiş trade kayıtları + evidence) olur.
- **REUSE (yeniden yazma):**
  - 3c `source_asset` tablosu + repo (`repositories/trading_signal.py::create_source_asset` — L1 için flush'lı) → ham TXT/CSV upload. Gerekirse `source_asset`'i domain-nötr bir isme/konuma taşımayı değerlendir (şu an `models/trading_signal.py` altında; 3d de kullanacağı için `models/source_asset.py`'a çıkarmak mantıklı — ama migration/ORM drift'e dikkat).
  - Generic `jobs` tablosu + `enqueue_job`/`send_job` (CR-09, `data` queue) → durable import job.
  - `s3/datasets.py::put_source_asset_bytes`/`get_raw_bytes` → ham bytes (testte monkeypatch).
  - 3a `attach_mainboard_item` (nested `run_idempotent key=None` = güvenli pass-through) / `patch_mainboard_item(pin_revision)` / `soft_delete_work_object`.
  - 3c pure-parser deseni (`domain/trading_signal/events.py`) → 3d için `domain/trade_log/records.py` benzeri saf parser/normalizer + skipped-row raporu.
- **YENİ:** `canonical_trade_record_batch` (immutable, parse edilmiş entry/exit kayıtları + accepted/skipped + evidence + content_hash, Save'de work_object_revision'a pinli) + `domain/trade_log/` (enums, config, compiler, records parser). Import worker `application/jobs/trade_log.py::run_import` + actor `run_trade_log_import`. Commands `application/commands/trade_log.py` (upload → request_import → create_trade_log_and_attach → create_trade_log_revision). Query `application/queries/trade_log.py`. Routes `apps/api/routes/trade_log.py` + main.py wire. Migration `0011_trade_log`.
- **Add Outsource Signal doc 03:** `start_external_work_object_draft(kind=trade_log)` opener 3a'da ZATEN var; sadece Trade Log save yolunu bağla.

## Bağlayıcı kurallar (Stage 3 acceptance)

`item_kind` strictly `{strategy, trading_signal, trade_log}` (mismatch → 422, CR-01) · Trade Log **ASLA PackageKind değil** (2f katalog dışlar) · pin by exact `root_id`+`revision_id` (L5) · `composition_hash` add/del/enable/pin'de değişir → prior Ready STALE; reorder/label değişmez · import_job durable/CR-09 (browser'dan bağımsız) · immutable revisions no-auto-repin (ilk Save&Add hariç) · save ≠ Ready PASS ≠ Run · tek-tx mutation+audit+outbox · optimistic concurrency (`expected_head_revision_id`/`expected_row_version`) · client-side parser otorite DEĞİL (worker canonical) · invalid rows silinmez, rapora girer.

## Yöntem (3b/3c dersi)

- **Workflow KULLANMA** — doğrudan kendin yaz, 3a/3b/3c pattern'lerini birebir izle (module-level async command'lar, `run_idempotent` op, `audit_repo.add_audit_event/add_outbox_event`, `request_context` dep, `ensure_can_edit/can_view`, GateGuard fact'lerini KISA geç).
- Lokal doğrula: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q` + **HER yeni `create_*` için L1 FK insert-order proof** (aiosqlite VEYA gerçek Postgres probe — 3c'de proof gerçek hatayı yakaladı, flush ile çözüldü).
- **Yerel Postgres:** `/opt/homebrew/bin` ile geçici cluster; `LC_ALL=C initdb --locale=C`, socket `/tmp/<kısa>`, role+db `entropia/entropia`, port 5432. Alembic komutları `LC_ALL=en_US.UTF-8` ile. (3c cluster'ı scratchpad'de bırakıldıysa yeniden kullan; yoksa kur.)
- Review CRITICAL/HIGH/ucuz-MEDIUM düzelt → commit (conventional) → PR → main → `gh run watch --exit-status` → **YEŞİL olunca merge için kullanıcıya sor** (main'e self-push/merge bloklu).
- Türkçe konuş, autonomous ilerle, ana kararları + PR linkini bildir, **MALİYET BİLİNÇLİ** (gerekirse dilimi böl), her checkpoint'te memory'ye yaz.

## 3c'nin bıraktığı takip notları (3d'yi etkileyebilir)

- `upload_source_asset` content-dedup `run_idempotent` dışında (zararsız yarış).
- V1 import canonical-column identity mapping (mapping profile/connector yok — file-source).
- Instrument Registry = string eşitlik (gerçek resolver Stage 5).
- `source_asset` şu an `trading_signal` modül altında — 3d paylaşacağı için ortak bir yere taşımayı düşün.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 3d başlat (Trade Log, doc 05). Add Outsource Signal'ın trade_log
save yolunu da bağla. Önce bağlamı oku, sonra working loop'a göre ilerle.

Durum: Stage 3c (Trading Signal) TAMAMLANDI, main'e merged (PR #10, main=49baed6,
Alembic head = 0010_trading_signal). Composition (3a) + Strategy (3b) + Trading
Signal (3c) hazır. Branch feat/stage-3d-trade-log AÇ (henüz yok).

ÖNCE OKU (otorite sırası): (1) docs/STAGE3D_KICKOFF.md — bu dilimin tam handoff'u,
tasarım pointer'ları, reuse listesi, working loop. (2) docs/STAGE2_HANDOFF.md →
"Stage 3c landed" + dersler L1–L7 + reusable foundation. (3) docs/STAGE_BUILD_PLAN.md
→ "Trade Log (05)" satırı + Stage 3 acceptance. (4) docs/spec/05_..Trade_Log.. →
spec'i TAM çıkar (field/import contract, command payloads, §9 domain, acceptance).
(5) ecc memory "Entropia Stage 3c — Trading Signal" checkpoint.

TASARIM: Trade Log = external work object (trade_log), historical entry/exit ledger
(canlı sinyal DEĞİL). 3c gibi NATIVE work object'i değerlendir (doc 05 §9 ile doğrula).
REUSE: 3c source_asset + repo (L1 flush'lı), generic jobs+enqueue_job (CR-09 data
queue), s3 put_source_asset_bytes/get_raw_bytes, 3a attach/pin/soft-delete, 3c pure-
parser deseni. YENİ: canonical_trade_record_batch (immutable parsed trade records +
accepted/skipped + evidence + content_hash, work_object_revision'a pinli) + domain/
trade_log/ + commands/jobs/queries/routes/trade_log.py + migration 0011_trade_log.

Bağlayıcı: item_kind {strategy,trading_signal,trade_log} (mismatch 422, CR-01);
Trade Log ASLA PackageKind; pin exact root+revision (L5); composition_hash STALE
semantiği; import durable/CR-09; immutable no-auto-repin (ilk Save&Add hariç);
save≠Ready≠Run; tek-tx mutation+audit+outbox; optimistic concurrency; client parser
otorite değil; invalid rows rapora girer.

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 3a/3b/3c pattern birebir. Lokal doğrula
(ruff+format+mypy+pytest + HER create_* için L1 FK proof). Yerel Postgres /opt/homebrew
LC_ALL=C initdb, socket /tmp, entropia/entropia:5432; alembic LC_ALL=en_US.UTF-8.
Review düzelt → commit → PR → main, gh CI izle, YEŞİL olunca merge için bana sor
(self-merge bloklu). Türkçe konuş, autonomous, MALİYET BİLİNÇLİ (gerekirse dilimi böl).
Her checkpoint'te memory'ye yaz. VE HER KAPANIŞ OTURUMDA: docs/STAGE3E_KICKOFF.md +
bir sonraki dilimin yapıştırmaya-hazır resume prompt'unu hazırla ve STAGE2_HANDOFF.md'yi
güncelle.
```
