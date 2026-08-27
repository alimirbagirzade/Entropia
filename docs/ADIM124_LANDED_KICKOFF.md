<!-- doc-status: historical -->

# ADIM 124 landed — `G14` Karar 1'in `B` yarısı sevk edildi (`NET` enum'dan düştü + kolon CHECK'i)

**Taban:** `8655e0fa` (ADIM 123 / `B0`, PR #858) · **yeni alembic head
`0044_drop_net_conflict_policy`** · `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi**
(`--check` exit 0) · golden **el değmedi** · `SHARED_ALLOCATION_STATUS` = `future_dev`
(`capability.py`'ye **hiç dokunulmadı**) · blocker **DEĞİŞMEDİ** (1 — yalnız A-08), BLOCKED.

---

## Nerede duruyoruz

`G14` (GH #544) dört kararlıydı; **dördü de imzalı**. Bu slice Karar 1'in `B` yarısını
**uyguladı**:

| Karar | İçerik | Durum |
|---|---|---|
| 1 | `C` şimdi + **`B` (KALDIR)** `C9` öncesi | `C` = ADIM 118 · **`B` = BU SLICE** |
| 2 | `B3` — `'NET'` satırı varsa migration **DURSUN** | ADIM 123 imza · **BU SLICE uyguladı** |
| 3 | `C`'nin metni (`_net_policy_warning`) | ADIM 118 · **bu slice metni SİLDİ** (konusu kalmadı) |
| 4 | `B0` — yazma yolunu dondur | ADIM 123 (#858) |

**`G14` KAPANMADI ve #544 KAPATILMADI** — kapatma `human-only`. Ön koşul **20 kırmızı
kalır**: satır issue'nun **kapanmasını** ister, kodun inmesini değil.

---

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

| Ne | Nerede |
|---|---|
| Migration (B3 halt + drift halt + CHECK) | `backend/alembic/versions/0044_drop_net_conflict_policy.py` |
| Kısıdın ORM ikizi (parite kapısı için) | `PortfolioAllocationPlan.__table_args__` → `ck_portfolio_allocation_plan_conflict_policy` |
| Daralan enum | `domain/allocation/enums.py::CrossItemConflictPolicy` (**2 üye**) |
| Genelleşen refüz | `execution/arbitration.py::resolve_policy` — `supported=False` dalı **korundu**, mesaj genelleşti |
| Jenerik UI guard'ı (**NET'e özel değil**) | `pages/Portfolio.tsx` `<select>` içindeki `disabled` option bloğu |

---

## DOKUNULMAYANLAR — ve neden (ölçüldü, tercih değil)

1. **`engine.py::conflict_downgraded_from_net` — SIFIR satır.** Enum'u değil, bir Backtest
   Result'ın **immutable `capital_execution` manifest snapshot'ından** gelen bir **dizeyi**
   karşılaştırır (`PortfolioRules.conflict_policy: str | None`). Pinlenmiş manifest
   **tarihsel kayıttır**; `"NET"`'i tuple'dan çıkarmak eski bir Result'ın replay'ini
   `downgraded_from_net` → `unknown` yapardı. **Kapılı:**
   `test_the_shipped_sequential_conflict_gate_is_untouched` o satırı kaynak düzeyinde pinler.
   → Devir notunun *"bunların HEPSİ ölü koda döner"* iddiası **bu yüzey için yanlış**.
2. **`capability.py` / `SHARED_ALLOCATION_STATUS`** — el değmedi.
3. **ADR-0002** — amendment **yazılmadı** (`A` seçilmedi).
4. **`arbitration.py::resolve_policy`'nin `supported=False` dalı** — sevk edilen tek
   `supported=False` satırı NET'ti, ama dalı silmek gelecekteki desteklenmeyen bir
   politikanın **sessizce koşmasına** izin verirdi (fail-closed → fail-open).

---

## Sıradaki kalem

Ön koşul defterine göre (`final_closure_delta_audit_2026-08-25.md` §10) sıra:
**`C6`'nın kalan yarısı** (`G11`/`G12` blocker'ları — #849'da imzalı, kod hâlâ inmedi),
sonra ön koşul 15–18 ve 22, **en son `C9`**.
**İnsan eylemi bekleyen:** #544'ün kapatılması (kapanış yorumu `B`'yi ve bu slice'ı
adlandırmalı, #558 emsali) ve #559'un kapanış yorumu.

---

## Paste-ready resume prompt

```
ENTROPIA — G14 `B` indi (0044); sıradaki kalem `C6`'nın kalan yarısı (G11+G12 blocker'ları)

ÖNCE DOĞRULA: git fetch && git log --oneline origin/main -6 && gh pr list --state open
  Yeni alembic head `0044_drop_net_conflict_policy` olmalı. `CrossItemConflictPolicy`
  iki üyeli olmalı (NET yok).

DURUM: G14'ün dört kararı da imzalı; `C` (ADIM 118), `B0` (#858) ve `B` (ADIM 124) indi.
  #544 HÂLÂ AÇIK ve kapatma `human-only` → ön koşul 20 kırmızı, kalan tek eylem insana ait.

GÖREV: `C6`'nın kalan yarısı — `G11` (P2) ve `G12` (P8) blocker'ları. İkisi de #849'da
  İMZALI; ADIM 119 ölçmüştü ki kod hâlâ inmedi (sıfır hit — YENİDEN ÖLÇ, bayatlamış olabilir).
  Kapsam ve gerekçe: docs/ADIM117_LANDED_KICKOFF.md + docs/ADIM119_LANDED_KICKOFF.md.

YASAKLAR: SHARED_ALLOCATION_STATUS'a DOKUNMA. ENGINE_VERSION/golden el değmez — oynuyorsa
  DUR ve raporla. #544/#559 human-only. ADR-0002'ye amendment yazma.
  `engine.py::conflict_downgraded_from_net` DOKUNULMAZ (manifest dizesi, kaynak-düzeyi ratchet'li).

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; exit code'u AYRI oku;
  yeni `create_*` varsa L1 FK insert-order proof + migration varsa alembic up/down/up
  ZORUNLU; GateGuard'da 4 olguyu sun; kapanış ritüeli ZORUNLU.

ORTAM NOTU (ADIM 124'te ölçüldü): bu makinede Postgres :5432 ayakta (entropia/entropia)
  ama worktree'de `backend/.venv` ve `frontend/node_modules` YOK — `uv sync --all-extras`
  ve `npm ci` gerekir. Tam backend suite 10 dk'yı AŞAR: arka planda tek çağrıda koştur,
  ortada kesme. `alembic upgrade head` için `LC_ALL=C.UTF-8 PYTHONUTF8=1`.
  Alembic revision id'si `varchar(32)`'yi AŞAMAZ (ADIM 124'te 33 karakterle patladı).
```
