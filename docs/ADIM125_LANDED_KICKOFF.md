<!-- doc-status: historical -->

# ADIM 125 landed — `C6` tamamlandı: `G11` (P2) + `G12` (P8) admission blocker'ları sevk edildi

**Taban:** `9179a1e8` (ADIM 124 = #859). Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 125.

---

## Nerede olduğumuz

`C6` **dört** admission blocker'ı istiyordu. ADIM 119 ikisini (OD-6(a), OD-1(a)) sevk
etmiş, diğer ikisini **bilerek yazmamıştı** — o an kapıları imzasızdı. #849 onları
2026-08-26'da imzaladı; bu slice ikisini de sevk etti.

| Ön koşul | Konu | Sahip | Durum |
|---|---|---|---|
| **#13** | P2 — ertelenen fill / bekleyen limit | insan → `G11` | ✅ **BU SLICE** |
| **#14** | P8 — paylaşımlı koşuda scaling | insan → `G12` | ✅ **BU SLICE** |
| **#15** | OD-6(a) — non-executing kind sleeve tutamaz | E6 | ✅ ADIM 119 |
| **#16** | OD-1(a) — mixed `record_time_basis` | E6 | ✅ ADIM 119 |

**`SHARED_ALLOCATION_STATUS` = `future_dev` (KALDIRILMADI)** · `ENGINE_VERSION`
**değişmedi** · migration **YOK** · OpenAPI **değişmedi (ölçüldü, exit 0)** · golden
**el değmedi** · `frontend/src` **sıfır satır** · blocker **1** (yalnız A-08), **BLOCKED**.

> **`C6`'nın kapanması lift DEĞİLDİR.** Dört guard da sevk edilen build'de
> **ULAŞILAMAZ** — containment 1 numaralı sert kapı olarak önce reddediyor. Bunlar
> `C9` bayrağı kaldırdığında hazır bulunması gereken fail-closed tabandır.

---

## Bu slice'ın bıraktığı REUSE çapaları (tam sembol adlarıyla)

**Yeni modül — TEK predicate, ÜÇ okuyucu:**
`domain/backtest/execution/shared_shapes.py`

- `unsupported_shared_shapes(config: StrategyConfig) -> tuple[SharedShapeViolation, ...]`
  — `(kind, field_path, detail)`. `detail` **motorun cümlesidir**; admission onu
  kullanıcıya göstermez ama taşır, ki iki yüzey aynı satırı farklı anlatmasın.
- `SharedShapeKind` — **yalnız iki üye** (`DEFERRED_FILL`, `SCALING`), yani yalnız
  imzalı kapılar. Üçüncü bir üye eklemek bir imza gerektirir;
  `test_shared_shapes.py::test_only_the_two_signed_gates_exist` bunu pinler.
- `IMMEDIATE_ORDER_TYPES` — `participant.py`'den **taşındı** (kopyalanmadı). Pozitif
  küme; bilinmeyen bir emir tipi **fail-closed** dinlenir sayılır.

**Motor tarafı:** `participant.py::_unsupported_shapes` artık taşınan satırları
`*((True, violation.detail) for violation in unsupported_shared_shapes(ctx.config))`
ile **geri ekler**. Çözülmüş bir `_RunConfig` isteyen satırlar (allocation'sız koşu,
plan yok, capability kapısı) orada **kaldı** — admission onları soramaz.

**Kullanıcıya görünen metinler:** `domain/allocation/shared_mode_admission.py` →
`DEFERRED_FILL_{MESSAGE,REMEDIATION}` · `SCALING_{MESSAGE,REMEDIATION}`. Bu modülün
*"kardeşidir, kopyası değil"* paragrafı **yeniden yazıldı**: OD-1/OD-6 hâlâ ayrık, ama
P2/P8 **bilerek aynı sorudur, iki kez** ve gerekçesi orada yazılı.

**İki yüzey, tek kurucu:**

- Ready Check → `readiness/validators.py::shared_mode_execution_issues(strategies)`
  (public; **parse edilmiş** config alır) + private
  `_shared_mode_execution_issues(items, *, allocation_enabled)`, `evaluate_readiness`
  içinden çağrılır. **`evaluate_readiness` imzası değişmedi** — yeni kwarg yok.
- Admission → `backtest_run.py::_admit_run_body` adım **3d**, `context.strategy_configs`
  üzerinden. Aynı fonksiyonu import eder.

**Sıfır ek sorgu:** `RunManifestContext` dördüncü bir alan kazandı —
`strategy_configs: list[tuple[str, StrategyConfig]]`. **Manifest grubu DEĞİLDİR ve
`build_run_manifest`'e verilmez**: `data_time` / `strategy_package` `execution_key`'e
hash'lenir, oraya alan eklemek her saklanan Result'ın reuse namespace'ini yeniden
bölerdi. `resolve_run_manifest_context`'in zaten parse ettiği configler taşınır.

**Kodlar:** `ReadinessIssueCode.ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED` ·
`…_SCALING_UNSUPPORTED`. **Migration YOK** — `readiness_issue.code` CHECK'siz varchar.

**Test çapaları:**

- `tests/unit/test_shared_shapes.py` — predicate. Timing kümeleri **türetilir**
  (`ExecutionModel.model_fields`'ten, **alan başına** — entry ve exit farklı literal
  kümeleri kabul eder, ölçüldü: `limit_fill_simulation` entry-only,
  `stop_limit_priority_simulation` exit-only).
- `tests/unit/test_shared_mode_admission.py` — issue şekli + kapsama kapısı.
- `tests/unit/oracles/test_oracle_engine_participant.py` — **parite** (beklenen cümle
  modülden türetilir, alıntılanmaz) + **bilerek dışarıda bırakılan** üç şekil.
- `tests/integration/test_shared_mode_admission.py::_attach_ready_strategy` artık
  `execution=` ve `scaling=` alır; **varsayılanı IMMEDIATE bir timing**.

---

## TUZAK — bunu bilmeden dokunma

**`_strategy_payload`'ın varsayılanı `next_candle_open`'dır, yani `G11`'i İHLAL EDER.**
Paylaşımlı bir kompozisyon kuran her fixture'ın `execution=` ile immediate bir timing
geçmesi gerekir; geçmezse koşu `ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED` ile
reddedilir ve test *"ilgisiz bir sebeple"* kırmızı olur. Varsayılan **bilerek
değiştirilmedi**: bir düzine bağımsız-mod fixture'ı ona dayanıyor ve `next_candle_open`
lookahead'siz kanonik seçimdir.

**Aynı tuzağın İKİNCİ yüzü:** `test_shared_clock_worker_branch.py` worker'ın fail-closed
yarısını kanıtlamak için **admission'ın geçirdiği ama motorun reddettiği** bir şekle muhtaç.
O yüzden `_loop_refused_payload` (immediate timing + şema varsayılanı `allow_stacking`)
`_shared_safe_payload`'dan **ayrıldı**. Stacking imzalanırsa o test kırmızıya döner — bu
kasıtlı, iniş yolu odur. Odaklı koşular bunu **yakalamadı**, tam suite yakaladı.

**`_readiness_blocked`'ın `details` anahtarı `field`'dır, `field_path` DEĞİL**
(`_issue_detail`). Rapor tarafında `field_path`'tir. İkisini karıştırmak `KeyError` verir.

**`details` WARNING'leri de taşır.** `{d["code"] for d in error.details} == {...}` yazma;
`severity == "blocker"` ile filtrele, yoksa ilgisiz bir `ALLOCATION_ISSUE` uyarısı testi
düşürür (ölçüldü).

---

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **Negatif kontrolü belleğe geri yaz, versiyon kontrolünden geri alma** — ağaçta
  commit'siz iş var. Harness `finally`'de restore eder ve her turdan sonra
  `git status` okunur.
- **Bir NC yalnız kırmızı vermekle yetinmez, NEYİN yeşil kaldığını da söyler.** NC-3
  bu slice'ta bir eksik assertion'ı ortaya çıkardı: entegrasyon testleri Ready Check
  yarısını hiç kanıtlamıyordu, çünkü admission hepsini yakalıyordu.
- **GateGuard:** yeni dosyayı Bash heredoc ile yaz. Ama **yıkıcı bir deseni İÇEREN
  heredoc da bloklanır** (eşleşme komut dizesinin tamamındadır) → o metni Write ile yaz.
- Alt küme koşarken **`--no-cov`** ekle; coverage kapısı tek dosyada sahte kırmızı verir.

---

## Sıradaki hamle

`C6` kapandı. Ön koşul defterinin kalan kırmızıları: **17** (OD-2 mark policy),
**18** (`CONTENTION_SELECTION_STATUS` flip), **20** (#544 kapansın — **insan**,
`human-only`), **22** (A15 bump + A16 manifest + A19 + A22, `C9`'un kendisi).

**Kod tarafındaki sıradaki kalem `C7`** (A16 manifest split). `C9` (lift) en sonda ve
ADR §16 **Gate 2** (`G10`) ayrı bir insan kapısıdır — 2026-08-26'da **`B` — ERTELE**
olarak imzalandı, yani red değil, **yeniden talep edilmeyi bekliyor**.

---

## Paste-ready resume prompt

```
ENTROPIA — C6 KAPANDI (ADIM 125). Sıradaki kalem C7 (A16 manifest split).

ÖNCE DOĞRULA (handoff BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -6 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3
  Dört C6 guard'ı da yerinde olmalı:
    grep -c "SharedShapeKind" backend/src/entropia/domain/readiness/validators.py   # >= 1
    grep -n "3d\." backend/src/entropia/application/commands/backtest_run.py

DURUM: C6'nın dört admission blocker'ı da indi (OD-6/OD-1 = ADIM 119, P2/P8 = ADIM 125).
  Hepsi containment'ın ARKASINDA ve sevk edilen build'de ULAŞILAMAZ — C9 için fail-closed
  taban. SHARED_ALLOCATION_STATUS hâlâ future_dev. Blocker 1 (yalnız A-08), BLOCKED.

GÖREV: C7 — A16 manifest split. Ön koşul defteri:
  docs/audit/closure_w0_containment_lift_preconditions_2026-08-17.md §2 (doc-status:
  historical, kolonu 0f0651d'de DONMUŞ — satırlara tarihli not eklenir, ❌ çevrilmez).

YASAKLAR: SHARED_ALLOCATION_STATUS'a DOKUNMA (lift = C9 + G10, ayrı insan kapısı).
  ENGINE_VERSION/golden el değmez — oynuyorsa DUR ve raporla. #544/#559 human-only.
  engine.py::conflict_downgraded_from_net DOKUNULMAZ (kaynak-düzeyi ratchet'li).
  execution/shared_shapes.py'ye İMZASIZ bir satır ekleme — kısmî kapanış / stacking /
  hedge bilerek dışarıda ve bir testle pinli.

TUZAK: _strategy_payload'ın varsayılan timing'i next_candle_open = G11 ihlali. Paylaşımlı
  bir fixture kuruyorsan execution={"entry_timing": "current_candle_close", ...} geç.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; exit code'u AYRI oku;
  alt küme koşarken --no-cov; GateGuard'da 4 olguyu sun; kapanış ritüeli ZORUNLU.

ORTAM: Postgres :5432 ayakta (entropia/entropia). backend/.venv yoksa `uv sync --all-extras`.
  Tam backend suite 10 dk'yı AŞAR: arka planda tek çağrıda koştur, ortada kesme.
```
