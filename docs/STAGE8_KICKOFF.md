# Stage 8 — End-to-End Integration & Hardening — Kickoff / Resume

> **Amaç:** Temiz oturumda kaldığımız yerden devam. Yapıştırmaya hazır resume prompt en altta.
> Stage 8 = SON aşama: e2e integration flow'ları + hardening (`STAGE_BUILD_PLAN.md` Stage 8).

## Nerede kaldık (2026-07-02)

- **Stage 0–7 TAMAMLANDI.** 7b (Future Dev, doc 22) PR **#32** MERGED → `main` = **`ef3e1c1`**
  (**git log ile doğrula** — özet stale-by-default). Alembic head = **`0020_future_dev`**
  (6 tablo: `future_capability` + `capability_activation_event` + `analysis_artifact` +
  `view_dataset` + `experiment_proposal` + `execution_plan`; 7 baseline slot Placeholder,
  id `fcap_<key>`). Test tabanı: **781 yeşil**. Tüm sayfa spec'leri (doc 01–22) landed.
- **Sıradaki = Stage 8 — e2e integration & hardening.** Branch `feat/stage-8-integration`
  (büyürse alt dilimlere böl: 8a integration flows / 8b hardening — kullanıcıyla teyitle).

## 7b'nin bıraktıkları (reuse anchor'ları — tam sembol adları)

- **`domain/capability`** — `CapabilityState` (7 state) + `ActivationGate` (7 gate) +
  `lifecycle.ALLOWED_TRANSITIONS` / `gate_issues` / `ensure_operational` /
  `snapshot_checksum`; `baseline.BASELINE_CAPABILITIES` (7 seed) + `STATE_MESSAGES` +
  Graphic View §4.1 copy. Registry satırları Retired olur, Trash'e gitmez.
- **`application/commands/capability`** — `transition_capability` (Admin route+service,
  non-empty reason, ZORUNLU idempotency key + `expected_registry_version` OCC
  `with_for_update`, tek-tx event+audit+outbox), `require_operational_capability`
  (inactive → `CAPABILITY_NOT_ACTIVE`, gate ÖNCE — CR-09 sıfır yan etki),
  `query_view_dataset` + `create_analysis_artifact` (`ANALYSIS_ARTIFACT_CAPABILITY`
  type→capability map).
- **CR-08 gateway gate'i** — `tool_gateway.CAPABILITY_GATED_TOOLS` +
  `exposed_tool_names(operational_keys)`; input: `capability_repo.
  operational_capability_keys(session)`. **7b DEFERRED → Stage 8 işi:** Coordinator
  plan adımı `exposed_tool_names`'i henüz TÜKETMİYOR — gateway-parity işinde bağla.
- **Test deseni** — `tests/integration/test_future_dev.py`: state-walk helper'ları
  (`_walk_to_limited`), OCC/stale, per-gate issue list, REJECTED tool kaydı,
  sıfır-yan-etki assert'leri; e2e testlerde şablon olarak kullan.
- **Genel (0–7):** one-tx no-commit + `run_idempotent` + `_audit_and_outbox`;
  `session.refresh(with_for_update=True)` OCC; L1 parent-before-child flush;
  advisory lock örneği `manual_repo.lock_stream` (210_721); opaque keyset cursor
  (`domain/agent_lab/cursor`); iki-fazlı purge (`application/jobs/purge`);
  outbox tablosu `audit_repo.add_outbox_event` her domain'de zaten yazılıyor.

## Stage 8 tasarım pointer'ları (`STAGE_BUILD_PLAN.md` Stage 8 satırı — TAM oku)

- **Backend hardening:** tüm domain'lerde outbox→SSE fan-out (SSE bugün yalnız agent
  events; `apps/api/sse.py` + outbox consumer genelle); Tool Gateway parity testleri
  (Agent tool ↔ insan komutu aynı policy sonuçları; `exposed_tool_names` Coordinator'a);
  cross-stage manifest reproducibility; retention/purge scheduler (`apps/scheduler`);
  rate limiting; CORS/security headers; per-process metrics (golden signals + queue
  depth + outbox lag + lease age).
- **Integration flow (a):** Market+Research ingest → approve → Create Package
  (Pre-Check→candidate→validate→approve/publish) → Strategy revision → Mainboard attach
  → Allocation → Ready Check → RUN → succeeded Result → History → Arrange Metrics →
  soft-delete → Trash → restore — TEK test akışı, pinned manifest'ten reproducible.
- **Integration flow (b):** Agent loop: directive → bundle resolve → backtest request →
  result linked → hypothesis — UI'dan bağımsız.
- **Acceptance:** identical re-run idempotent result reuse; failed/cancelled asla
  Result/History üretmez (CR-03); her mutation audited+outboxed; "latest" leak yok;
  soft-delete tarihsel pinned manifest'i kırmaz; Agent kendi output'u dışına çıkamaz;
  INF-01..INF-10 yeşil; secrets log/audit/frontend build'de yok; deployment topolojisi
  (api + 4 worker plane + agent-coordinator + scheduler + postgres/redis/minio) boot +
  health/ready.

## Yöntem (5a→7b dersleri — birebir)

- **Workflow KULLANMA** — doğrudan yaz. YENİ dosya = Bash heredoc (gate-free); mevcut
  dosya Edit → 4-fact. `cd backend`.
- Lokal doğrula: `uv run ruff check . && uv run ruff format --check . && uv run mypy src`
  + `DATABASE_URL=... uv run pytest --no-cov -q` (**781 mevcut test yeşil kalmalı**);
  yeni migration gerekirse `0021_*` (→0020) up/down/up + parity; her yeni `create_*`
  için L1 FK proof.
- **code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA** (6b: 3/5 false-positive;
  6c: 2/2 gerçek; 7a: 0; 7b: 0 — HER ZAMAN doğrula) → commit (conventional, attribution
  YOK) → PR → `gh pr checks <n> --watch` → **merge için kullanıcıya sor**.
- Türkçe, autonomous, **MALİYET BİLİNÇLİ**. Kapanışta: handoff + CLAUDE.md + memory
  (ecc graph + claude-mem); Stage 8 sonrası proje V1 tamam → kapanışta "post-V1"
  durumu netleştir.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 8 başlat: End-to-End Integration & Hardening. Önce bağlamı oku,
working loop'a göre ilerle. Branch feat/stage-8-integration AÇ (kapsam büyürse 8a/8b
bölünmesini bana sor). MALİYET BİLİNÇLİ ol.

Durum: Stage 0–7 TAMAMLANDI (7b Future Dev PR #32 merged). main = ef3e1c1 (git log ile
DOĞRULA — özet stale-by-default). Alembic head 0020_future_dev. 781 test yeşil. Yeni
migration gerekirse 0021_* (→0020).

ÖNCE OKU (otorite sırası): (1) docs/STAGE8_KICKOFF.md — bu dilimin tam handoff'u.
(2) docs/STAGE2_HANDOFF.md → "Stage 7b landed (PR #32)" + "Next: Stage 8". (3)
docs/STAGE_BUILD_PLAN.md "Stage 8" satırı TAM (backend hardening + iki integration flow
+ acceptance + INF-01..INF-10). (4) mevcut kod: apps/api/sse.py + audit_repo outbox
(fan-out genellemesi), apps/scheduler (retention/purge scheduler), domain/agent_lab/
tool_gateway.exposed_tool_names + repositories/capability.operational_capability_keys
(Coordinator'a bağlanacak — 7b deferred), apps/agent_coordinator (plan adımı),
tests/integration/test_future_dev.py (_walk_to_limited + sıfır-yan-etki assert şablonu),
docs/spec/Entropia_V18_Master_Technical_Reference (INF-01..INF-10 + Modül 19/20).

TASARIM: (a) tam pipeline integration testi: ingest→approve→Create Package→Strategy→
Mainboard→Allocation→Ready Check→RUN→Result→History→Arrange Metrics→soft-delete→Trash→
restore (pinned manifest reproducibility + CR-03 assert'leri); (b) UI-bağımsız Agent
loop testi: directive→bundle resolve→backtest request→result→hypothesis; outbox→SSE
fan-out tüm domain'ler; Tool Gateway parity (+ exposed_tool_names Coordinator wiring);
retention/purge scheduler; rate limiting; CORS/security headers; metrics (golden
signals + queue depth + outbox lag + lease age); deployment health/ready.

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 7b pattern birebir. YENİ dosya Bash heredoc;
mevcut dosya Edit 4-fact. cd backend. ruff+format+mypy+pytest (781 yeşil kalmalı);
migration gerekirse 0021 up/down/up + parity + L1 FK proof. code-reviewer subagent →
CRITICAL/HIGH AMPİRİK DOĞRULA → düzelt → commit (conventional, attribution YOK) → PR →
gh pr checks --watch → YEŞİL olunca merge için bana sor. Türkçe, autonomous, MALİYET
BİLİNÇLİ. Kapanışta: handoff + CLAUDE.md + memory (ecc graph + claude-mem) + post-V1
durum özeti.
```
