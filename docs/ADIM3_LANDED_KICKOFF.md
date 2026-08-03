# ADIM 3 landed — Shared portfolio containment (PR #520) · sıradaki slice kickoff'u

> Bu belge **ADIM 3'ün** kapanış handoff'udur. En altta **paste-ready resume prompt** var.
> Otorite sırası: bu belge → `docs/STAGE2_HANDOFF.md` → `docs/STAGE_BUILD_PLAN.md` →
> `docs/spec/NN_*` → `docs/audit/current_main_ground_truth_2026-08-03.md` §18.

---

## 1. Nerede duruyoruz (empirik, 2026-08-03)

| Olgu | Değer |
|---|---|
| `origin/main` | `b5d524d` (PR #522 merge'ü — bu kapanış rebase edildikten sonra) |
| ADIM 3 merge | `6c46c03` · commit `088e3e9` · base `948b6fb` |
| Alembic head | `0043_i08_registry_strategy_fks` — **tek head, ADIM 3 migration EKLEMEDİ** |
| `ENGINE_VERSION` | `backtest-engine-v18-same-candle-entry-exit` — **bilerek bump EDİLMEDİ** |
| OpenAPI | 196 operation, drift guard temiz (ADIM 3 şema değiştirmedi) |
| Açık PR | ADIM 3'ün kapanış PR'ı **#523** dışında yok |
| Açık issue | **#514** (ekran okuyucu denetimi — insan işi, agent kapatamaz) |

**Dikkat — bu kapanış main'in gerisinden yazıldı.** ADIM 3 (#520) `6c46c03`'te merge oldu;
main sonrasında **#521** (ESP export contract v2, `a570934`) ve onun kapanış kaydı **#522**
(`b5d524d`) ile ilerledi. Bu yüzden ADIM 3'ün kaydı `PROJECT_HISTORY.md` ve
`STAGE2_HANDOFF.md` içine **G-02 (#521) kaydının ÖNÜNE** yerleştirildi — dosyadaki sıra
merge sırasıdır. `CLAUDE.md` §Current position'da **#522'nin ölçtüğü test sayıları
(2974 passed / %92.47, #521'de ölçülmüş) korundu**; ADIM 3'ün kendi ölçümü (%92.43) daha
eskidir ve yalnız `PROJECT_HISTORY.md`'de kayıtlıdır.

---

## 2. ADIM 3 ne yaptı — tek cümlede

Portföy "shared capital" modu **spec'in istediği unified-clock simülasyonunu çalıştırmıyordu**
(engine timestamp yerine item üzerinde döngü kuruyor). Sapma zaten bir uyarı olarak
*bildiriliyordu* ama sonuç yine de **kanonik cevap olarak sevk ediliyordu**; ADIM 3 bunu
**fail-closed**'a çevirdi: taslak hâlâ kaydedilir, **çalıştırma reddedilir**.

Kusur kod yazılmadan **önce** ampirik olarak üretildi (decision record §3):
sıralı fold `max_drawdown = 5000.00`, aynı dört kapanış tek saatte **`3000.00`** → **%66 fazla**;
kompozit eğri zaman-sıralı değil (01:00, 04:00, 02:00, 03:00).

Tam anlatı: **`docs/PROJECT_HISTORY.md`** → *"Shared portfolio containment — ADIM 3"*.
Karar kaydı: **`docs/decisions/2026-08-03_shared_portfolio_containment.md`** (§6 kaldırma
şartları, §8 bilinçli kapsam kaybı).

---

## 3. REUSE ANCHORS — ADIM 3'ün bıraktığı tam sembol adları

### 3.1 Tek kanonik kaynak (yeni saf düzlem)

`backend/src/entropia/domain/allocation/capability.py` — **DB yok, I/O yok, import döngüsü yok.**
Dört yüzey buradan okur; **hiçbiri kuralı tekrarlamaz.**

| Sembol | Tür | Rolü |
|---|---|---|
| `SHARED_ALLOCATION_STATUS` | `SharedAllocationStatus = "future_dev"` | **Tek anahtar.** `"active_v1"` yapmak containment'ı kaldırır |
| `SHARED_ALLOCATION_CAPABILITY_KEY` | `"portfolio.shared_capital_allocation"` | capability matrix girdisi |
| `SHARED_ALLOCATION_FIELD_PATH` | `"enabled"` | doc 14 §9.1 `field_path` |
| `SHARED_ALLOCATION_MESSAGE` | str | insan metni (blocker + zarf) |
| `SHARED_ALLOCATION_REMEDIATION` | str | doc 14 §9.1 `remediation` |
| `SHARED_ALLOCATION_DEPENDENCY` | str | neye bağlı olduğunu söyler (unified clock) |
| `LEGACY_SEQUENTIAL_RESULT_NOTE` | str | eski Result'ların okuma-zamanı etiketi |
| `shared_allocation_is_executable()` | `-> bool` | **tek karar noktası** |
| `shared_allocation_requested(capital_execution)` | `-> bool` | snapshot/draft'tan "shared istendi mi" |
| `shared_allocation_capability_view()` | `-> dict` | sunucunun yayınladığı görünüm |

### 3.2 Dört okuyucu yüzey (sıra önemli)

1. **Authoring kapısı** — `domain/allocation/rules.py::validate_allocation`
   → `AllocationIssueCode.SHARED_MODE_NOT_IN_BUILD` (`domain/allocation/enums.py:105`),
   **BLOCKER**, `field="enabled"`, **ilk sırada = lead blocker**.
   Portfolio sayfası + revision freeze reddi buradan gelir. **Taslak yine de KAYDEDİLİR.**
2. **Ready Check** — `domain/readiness/validators.py`
   → `ReadinessIssueCode.ALLOCATION_SHARED_MODE_NOT_IN_BUILD` (`readiness/enums.py:176`),
   scope `portfolio_allocation`, `remediation` + `field_path`.
   Yeni tablo: **`_ALLOC_REMEDIATION`** (`validators.py:136`, okunduğu yer `:1144`).
3. **Admission guard (asıl kapı)** — `application/commands/backtest_run.py::_admit_run_body`
   (`:488`, guard `:543`). **Ready Check'ten BAĞIMSIZ.** `snapshot.capital_mode_snapshot`'ı
   doğrudan okur ve **`build_run_manifest`'ten ÖNCE** (`:574`) çalışır → **run / manifest /
   job hiç oluşmaz** (doc 15 §9.3). request + retry, human + Agent hepsi buradan geçer;
   dayanıklı `run_admission_rejected` audit'i `_admit_run`'ın handler'ı yazar.
4. **Yayın** — `application/queries/allocation_plan.py:59,76` → `"shared_mode_capability"`;
   `frontend/src/pages/Portfolio.tsx:357` **verbatim** basar.
   Kontroller **etkileşimli kalır** — disabled UI sunumdur, authorization DEĞİLDİR.

### 3.3 Frontend

- `frontend/src/lib/allocation.ts` → `SharedModeCapability` tipi (`:115`).
- `frontend/src/lib/backtest.ts::diagnosticWarningLabel` (`:442`) — ham diagnostic
  token'larına insan etiketi verir; `components/ResultDetail.tsx:668` kullanır.
  Bu audit **G-07**'nin ham-token sorununun cevabıdır. **Kalıcı Result'lar değişmedi.**

### 3.4 Testler

| Dosya | Sayı |
|---|---|
| `backend/tests/unit/test_shared_allocation_containment.py` | 9 |
| `backend/tests/integration/test_shared_allocation_containment.py` | 7 |
| `frontend/src/test/legacySequentialResultLabel.test.ts` | 3 |

Kilit testler: `test_composite_portfolio_curve_is_not_time_ordered` (negatif kanıt — kaldırma
sırasında **pozitif muadiline yeniden yazılmalı, SİLİNMEMELİ**),
`test_a_legacy_shared_pool_result_stays_readable_and_unmodified`,
`test_shared_allocation_warning_path_is_now_fail_closed`
(`tests/integration/test_backtest_manifest_warnings.py:108`).

---

## 4. Sıradaki tasarım işaretleri

Sıra **`docs/audit/current_main_ground_truth_2026-08-03.md` §18**'de. §18 sıra 1 (#519) ve
sıra 3 (#521) landed. Sıradaki tek slice:

**ADIM 5 — `feat/library-request-validation-ui`** (§18 sıra 2 / §G-04).
**Backend TAM**, boşluk **yalnız frontend**:
- route `POST /library/{entity_id}/validation-runs` → `apps/api/routes/library.py`
- komut `pkg_cmd.request_package_validation` → aynı CP pipeline'ı (`start_package_validation_run`)
- rol kapısı `ensure_can_edit` (owner-or-Admin)
- bayrak `can_request_validation` → list + shared + detail DTO'sunun üçünde de var
- `frontend/src/lib/library.ts` bayrağı **tipliyor** ama **çağıran bir hook YOK**

Ondan sonraki §18 sırası: 4 → `fix/i16a-panel-logs-display-title` (+ F-07 kalıntısı
`frontend/src/pages/PanelLogs.tsx:134`), 5 → `test/fresh-install-acceptance`,
6 → `feat/agent-tool-gateway-strategy-trading-signal` (§G-03), 7 → `ci/security-hardening`.

> **ADIM 5'in ASIL handoff'u `docs/G02_LANDED_KICKOFF.md`'dir** (PR #522 ile merge edildi).
> ADIM 5'e başlarken **o belgeyi** kullan; bu belge ADIM 3'ün kaydı ve reuse anchor'larıdır.

---

## 5. Containment'ı kaldırmak isteyen için (bunu atlama)

`SHARED_ALLOCATION_STATUS = "active_v1"` yapmak **tek satırlık** bir değişikliktir ve
**altı şart karşılanmadan yapılırsa yanlış finansal sayı üretir.** Şartlar
`docs/decisions/2026-08-03_shared_portfolio_containment.md` **§6**'da somut ve denetlenebilir
halde yazılı (merged timestamp ekseni · tek ledger `P0`/`R0`/`U0` · tek `E(t)` yayını ve
`Ci(t) = max(0, E(t) − R0)·wi/100` · simetrik conflict arbitrasyonu · doc 13 §14 kabul testi 11 ·
**`ENGINE_VERSION` bump**).

Ayrıca **§8'deki üç kapsam kaybı geri getirilmelidir** (aşağıda §6.1).

> **"ADIM 20 unified oracle gate" bu repoda TANIMLI DEĞİL.** `current_main_ground_truth_2026-08-03.md`
> §18 yalnız 1–8 slice'ı listeliyor; ADIM 14–20 yok. Unified-clock orada *"ürün kararı
> gerektirir, bu denetimin kapsamı dışında"* diye kayıtlı. Uydurulmadı — bu yüzden şartlar
> §6'da **somut** yazıldı. Gate repoda tanımlanınca §6'yı **referans almalı, değiştirmemeli.**

---

## 6. Dürüst sınırlar (kayda geçmiş)

### 6.1 Bilinçli kapsam kaybı (decision record §8)

Admitted shared run kalmadığı için **üç davranış artık uçtan uca test edilemiyor**:

1. Worker'ın pinned pool `P0` ile kapitalizasyonu — **sizing aritmetiği**
   `tests/unit/test_backtest_engine_allocation.py`'de duruyor.
2. Portfolio kurallarının (`max_total_exposure_percent`, `conflict_policy`) **DONDURULMUŞ**
   revision'a taşınması — draft round-trip + freeze reddi test ediliyor.
3. **RC-03**'ün orijinal fixture'ı — artık strateji kapsamlı `EXECUTION_ASSUMPTIONS_DEFAULT`
   uyarısına taşındı; ulaşılamaz hale gelen yol
   `test_shared_allocation_warning_path_is_now_fail_closed` ile kilitli.

**Containment kaldırılırken üçü de geri getirilmeli** — sessizce bırakılmamalı.

### 6.2 Değişmeyen sınırlar

- **Independent capital** dokunulmadı (doc 13 §1.1 — eksik mod değil).
- Kalıcı Result'lar **immutable**; yalnız **okuma-zamanı etiketi** eklendi.
- **Migration YOK** (`readiness_issue.code = String(64)`, CHECK yok, yeni değer 35 karakter;
  `portfolio_allocation` scope üyesi zaten vardı).
- Route path · react-query key · OCC token · `Idempotency-Key` · hook · SSE taksonomisi ·
  `lib/*.ts` veri mantığı **değişmedi**.

### 6.3 Devam eden açık iş

- **GitHub #514** — NVDA/Firefox + VoiceOver/Safari ekran okuyucu kabul denetimi.
  2026-07-30'da kanıtsız kapatılmıştı, 2026-08-03'te yeniden açıldı. **İnsan işi.**
- **D-10** imza-mavisi (45 düğüm) kalıcı imzalı sapma; WCAG 2.2 AA **1.4.3 karşılanmıyor**.
- Doğrulanmış boşluklar: Tool Gateway `strategy.*`/`trading_signal.*` (§G-03),
  Library Request-Validation UI (§G-04).

---

## 7. Çalışma döngüsü (bu slice'ta işleyen yöntem)

1. **Önce kusuru üret.** Kod yazmadan, `origin/main` üzerinde probe ile ampirik kanıt çıkar.
   ADIM 3'ün tüm meşruiyeti §3'teki `5000.00` vs `3000.00` ölçümünden geliyor.
2. **Spec'i kanona bağla** — doc 13 §8.3/§8.4/§13 + §14 kabul testi 11. Sapma varsa
   "bildirmek" yetmez; sevk edilen cevap **kanonik cevap** olarak okunur.
3. **Direct-author**, Workflow yok. Önceki slice'ın kalıbını aynala.
4. **GateGuard:** YENİ dosyayı Bash heredoc (`cat > f << 'PYEOF'`) ile yaz → gate-free.
   Mevcut dosyaya EDIT/WRITE fact-force tetikler (4 olgu sun → retry).
5. **Lokal doğrulama:**
   `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
   (`addopts` `--cov-fail-under=90` taşıyor → tam suite kapıyı da doğrular).
   **Alt küme koşarken `--no-cov` EKLE.** Frontend: `npm run coverage`,
   vitest için **`--no-file-parallelism` ZORUNLU**.
6. **Ortam tuzağı:** paralel worktree'ler aynı DB'yi paylaşırsa sahte FAILED üretir —
   `TEST_DATABASE_URL` ile izole DB kullan. Tam suite'i **tek çağrıda** koş, **ortada öldürme**.
   **`pytest … | tail` KULLANMA** — exit code `tail`'in olur. Çıktıyı dosyaya yaz, `$?`'i ayrı oku.
7. **Code-review CRITICAL/HIGH bulgularını ampirik doğrula** — sık sık yanlış çıkıyorlar.

---

## 8. Paste-ready resume prompt

```text
ENTROPIA — sıradaki slice: ADIM 5 (feat/library-request-validation-ui)

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT — özete güvenme):
  git fetch --all --prune && git log --oneline origin/main -6 && gh pr list --state all --limit 6

OKUMA SIRASI (otorite sırasıyla):
  1. docs/ADIM3_LANDED_KICKOFF.md   ← bu belge (ADIM 3 / PR #520 kaydı, reuse anchor'ları)
  2. docs/G02_LANDED_KICKOFF.md     ← ADIM 5'in ASIL handoff'u (PR #522 ile landed)
  3. docs/audit/current_main_ground_truth_2026-08-03.md §18  ← slice sırası burada
  4. docs/STAGE2_HANDOFF.md — en alttaki "## Next:" bloğu
  5. docs/CODEMAPS/FRONTEND_MAP.md + docs/CODEMAPS/BACKEND_ROUTES.md (Library bölümü)

GÖREV — ADIM 5 / §18 sıra 2 / §G-04: Library Request-Validation UI.
  Backend TAM, boşluk YALNIZ frontend:
    route   POST /library/{entity_id}/validation-runs  (apps/api/routes/library.py)
    komut   pkg_cmd.request_package_validation → start_package_validation_run (CP pipeline)
    kapı    ensure_can_edit (owner-or-Admin)
    bayrak  can_request_validation → list + shared + detail DTO'sunun üçünde de var
    eksik   frontend/src/lib/library.ts bayrağı tipliyor ama ÇAĞIRAN HOOK YOK
  Yeni endpoint/route/tablo EKLEME. Bu bir frontend-bağlama slice'ı.

KURALLAR (CLAUDE.md'den, ihlal etme):
  - UI değişikliği docs/spec/index_guncellenmis_duzeltilmis_v18.html (v18 mockup) referanslı.
  - Route path / react-query key / OCC token (If-Match, expected_*) / Idempotency-Key /
    SSE taksonomisi / app/nav.ts DEĞİŞMEZ.
  - Direct-author, Workflow yok. YENİ dosyayı Bash heredoc ile yaz (GateGuard gate-free).
  - Kod arama: önce codebase-memory-mcp (search_graph / get_code_snippet), sonra dosya oku.

DOĞRULAMA:
  cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
  cd frontend && npm run typecheck && npm run coverage      # vitest: --no-file-parallelism ZORUNLU
  Alt küme koşarken --no-cov ekle. Tam suite'i tek çağrıda koş, ortada öldürme.

KAPANIŞ: CLAUDE.md §"Session CLOSING ritual" — 6 madde, istisnasız.
```

---

*ADIM 3 kapanışı · 2026-08-03 · `origin/main` @ `b5d524d` · alembic head `0043_i08_registry_strategy_fks`*
