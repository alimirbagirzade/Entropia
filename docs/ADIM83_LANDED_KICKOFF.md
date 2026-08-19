<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM85_LANDED_KICKOFF.md`'dir.**
> Bu belge yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat
> olabilir. Sayısal gerçekler için otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 83 LANDED — kabul borcu batch 11 (doc 18 backend) · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 83. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Kapanış yazılırken main **`aecd72c`** (ADIM 82 = #778 son kayıt). **Ürün kodu değişmedi**:
  migration yok, OpenAPI değişmedi, `ENGINE_VERSION` değişmedi,
  `SHARED_ALLOCATION_STATUS` = `future_dev`. Diff `backend/src` ve `frontend/src` altında **boş**.
- **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- Kabul borcu tavanı **yeniden donduruldu**: `partial` **86**, `uncovered` **8**,
  `debt_class` **A=1 · B=55 · C=6 · D=32**, `total_criteria` **383** (TABAN).
  Clause düzlemi: `covered` **1028**, `uncovered` **99**.
  **Bu sayıları buradan alma** — `docs/audit/acceptance_coverage_baseline.json` `.ceilings`
  otoritedir ve senden önce başka bir batch inmiş olabilir.
- **Doc 18'in backend'de test edilebilir borcu bitti.** Doc 03 ve doc 07 daha önce bitmişti.

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam dosya/sembol adlarıyla)

- `backend/tests/integration/test_analysis_lab.py`
  - `::test_directive_queue_writes_an_audit_row_for_that_directive` — audit + outbox satırını
    **hedef id'ye kapsayarak** okumanın deseni (`AuditEvent.target_entity_id`,
    `OutboxEvent.resource_id`). Yeni bir agent komutunun emission'ını asserted etmen gerekirse
    bunu kopyala; **bare count kullanma**, herhangi bir aktiviteyle yeşile döner.
  - `::test_supervisor_lifecycle_denial_leaves_the_runtime_untouched` — "red satırı kıpırdatmadı"
    deseni: satırı **geri oku**, sonra red **öncesi** `expected_row_version` ile meşru bir kontrol
    sür. Sessizce artmış bir `row_version` hayalet 409 üretir; yalnız ikinci yarı bunu yakalar.
  - `::test_empty_directive_rejected` — reddin ardından **dört model birden** sayılıyor
    (`TaskDirective`, `AuditEvent`, `OutboxEvent`, `AgentEvent`).
- `backend/tests/integration/test_agent_executor.py`
  - `::test_stop_after_admission_cancels_before_the_engine_and_publishes_no_result` — **bu partinin
    en değerli çapası**. Durable executor'ı sürerken bir kontrolü **belirli bir faz sınırında**
    enjekte etme deseni: `agent_executor._checkpoint` sarılır, `stage == "backtest_requested"`
    olduğunda üretimdeki `agent_control.stop_run` çağrılır, sonra üretimdeki
    `_pending_control_interrupt` kendi işini yapar. Aynı desenle **herhangi bir** faz sınırında
    pause/stop sürebilirsin.
  - Harness `test_e2e_agent_loop.py`'den ithal: `_seed_runtime_and_principals`, `_approved_market`,
    `_real_package`, `_agent_composition`, `_e2e_bars`; yerel `_queue_directive_and_spawn_job`
    Coordinator yarısını (directive → task → executor Job) tek çağrıda kuruyor.
- `backend/tests/integration/test_agent_tool_gateway.py`
  - `::_research_root_and_revision` — **kökü de** döndüren yardımcı (mevcut `_research_revision`
    yalnız revision id verir, bu yüzden drift testi kurulamıyordu).
  - `::test_new_dataset_revision_does_not_slide_into_a_pinned_context_manifest` — pin-drift
    deseni: `research_repo.append_research_dataset_revision(session, root, …)` kök head'ini
    ilerletir, sonra **üç bağımsız okuyucu** geri okunur (durable `AgentToolCall.response_ref`,
    `agent.task.query`, drift **sonrası** yazılan checkpoint).

## Pazarlıksız — bu slice'ın öğrendikleri

1. **"Result yok" iddiasını Result üretebilecek bir dünyada ölç.** Hiç backtest admit etmeden
   `BacktestResult == 0` demek totolojidir. `AL-10` ancak `BacktestRun` satırı **varken** ve
   `run_backtest` **bir sonraki satırdayken** anlamlıdır.
2. **Bir guard'ı mutasyonun altına taşımak istisnayı aynı şekilde fırlatır.** Bu yüzden
   `pytest.raises` tek başına bir "durum değişmedi" clause'unu **hiçbir zaman** kapatmaz — satırı
   geri oku. `AL-09`'un negatif kontrolünde `test_supervisor_lifecycle_denied` yeşil kaldı.
3. **`agent.task.query` `observation` scope ister.** `research` ile çağırınca çağrı REJECTED olur
   ve zarf `context_manifest_id` taşımaz → `KeyError`. Yeni bir gateway assertion'ında
   **`status == "succeeded"` de assert et**, yoksa reddedilmiş bir çağrıyı ölçtüğünü fark etmezsin.
4. **Semantik haritada `notes` bir YAML skaler'dır.** İçine `: ` ya da `''` koyacaksan bloğu
   **tek tırnaklı** skalere çevir; düz (plain) skalerde `mapping values are not allowed here`
   alırsın. Harita 1.2 MB — düzenlemeyi elle değil betikle yap ve hemen `--root ..` ile doğrula.
5. **Test ekleyen slice üretilmiş olguları TAZELEMELİ.** `repository_facts` "collected" sayısını
   taşır (3670 → 3674) ve `--check` bloklayıcıdır; README'nin generated bloğu da onunla üretilir.
6. **Bir clause'un yüzeyi kriterin sınıfını değiştirmez.** `AL-06.c3` frontend olduğu için açık
   kaldı; bu bir **bulgu değil**, sıradan sınıf-B borcudur ve `AL-06` sınıf B'de bırakıldı.
   Yeniden sınıflandırma tavanı **yükseltir** = adjudication.

## Sıradaki tasarım işaretleri — ÖNCE ÖLÇ

- **Kabul borcu hattı — doc 18 FRONTEND partisi (tek satır).** `AL-06.c3`: *"textarea texti
  kullanıcıda korunur"*. `frontend/src/test/analysisLab.test.tsx`'te **hiç** directive doğrulama
  testi yok. Kapatan test reddedilen submit'ten sonra textarea'nın **dolu** kaldığını sürmeli;
  negatif kontrol = başarı yolunda temizlenen alanı red yolunda da temizlemek. Kapanırsa `AL-06`
  covered olur ve **`debt_class` KALDIRILMALI** (`DEBT_CLASS_NOT_ALLOWED`).
- **Sıradaki daha büyük sınıf-B belgeleri (ölç, bu listeye güvenme):** doc 02 (8 partial),
  doc 05 (8 partial), doc 17 (7 partial), doc 10 (6 partial), doc 12 (6 partial).
  `--report`'un *Partial criteria* tablosunu oku; her satırın `notes`'u **nerede** eksik olduğunu
  yazıyor. **Parti seçmeden önce davranışın `backend/src`/`frontend/src`'te sevk edildiğini
  doğrula** — sevk edilmemişse sınıf yanlıştır, o bir **bulgudur**, parti değil.
- **KAPATMAYA ÇALIŞMA — açık bulgular:** `TL-11.c3`, `TL-16`, `TL-01.c4`, `RD-01.c4`, `RD-05.c5`,
  `RD-12.c4`, `RD-13.c4`, `PC-20.c3`, `PC-02.c2`, `TS-07.c2` — ve **yanlışlanamaz** olarak
  imzalı dördü: `TS-02.c2`, `AOS-04.c2`, `AOS-06.c2` (+ `PC-02.c2`). Sonuncular
  `unfalsifiable: true` taşır, tavandan **düşmezler**.
- **Mühendislik hattı — `C3`** (`execution/participant.py` adaptörü). Importer-allowlist kararı
  **#761'de imzalandı (Seçenek A)**; **negatif kontrol zorunlu** — sahte bir importer kapıyı
  gerçekten kırmızıya çevirmeli. Bu hat bu slice'tan **bağımsızdır**.

## Çalışma yöntemi (bu dalgada işe yarayan)

- Bu container'da **Postgres yok ama kurulabilir**: `pg_ctlcluster 16 main start`, sonra
  `entropia` rolü + `entropia` DB. Integration suite'i onsuz **sessizce skip** eder — yani
  "yeşil" hiçbir şey kanıtlamaz. Koşmadan önce `pg_isready` ile **ölç**.
- Alt küme koşarken **`--no-cov`** (yoksa coverage kapısı sahte kırmızı verir) ve
  **`-p no:randomly`** (negatif kontrolü tekrarlanabilir yapar).
- Negatif kontrolü **üretim dosyasının pristine kopyası** üzerinden yap (`cp` ile yedekle,
  kontrolü uygula, koş, geri yükle, `git status` ile **sıfır ürün değişikliği** doğrula).
- Kapı sırası: `ruff check` → `ruff format` → `mypy src` → hedefli pytest → `--ratchet` →
  `generate_repository_facts.py --check` → `node scripts/memory_index.mjs --check` (**repo kökünden**).
- `frontend/node_modules` bu container'da **yok**; frontend'e dokunmayan bir slice'ta bu bir
  sınırdır, hata değil — **yaz ve CI'a bırak**.

## Paste-ready resume prompt

```
ENTROPIA V18 — sıradaki slice

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, tavanı ya da PR durumunu bu prompttan alma.
  git fetch --all --prune && git log --oneline origin/main -8
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  Canlı kickoff'u BULDUR (adıyla arama):
    for f in $(git ls-tree -r --name-only HEAD -- docs | grep -E 'KICKOFF.*\.md$'); do
      head -3 "$f" | grep -q 'doc-status: current' && echo "$f"
    done
  TAVANI DOSYADAN OKU: docs/audit/acceptance_coverage_baseline.json .ceilings
  (bu satır yazılırken 86 partial / 8 uncovered / A1 B55 C6 D32, total 383 idi — BAYAT)

BAŞLAMADAN ÖNCE ÇAKIŞMA ARA:
  mcp__github__list_pull_requests(state=open) → dokunacağın dosyaya dokunan açık PR
  var mı? Kabul defteri SERİ bir kaynaktır — paralel bir batch varsa ikinci inen
  rebase edip YENİDEN DONDURUR.

HAT A — kabul borcu batch 12. Doc 03, 07 ve doc 18'in BACKEND'i bitti.
  En ucuz iş: doc 18 FRONTEND, tek satır AL-06.c3 (reddedilen directive submit'inden
  sonra textarea dolu kalır; frontend/src/test/analysisLab.test.tsx'te hiç directive
  doğrulama testi yok). Kapanırsa AL-06 covered olur → debt_class KALDIRILMALI.
  Daha büyük belgeler: doc 02 / 05 / 17 / 10 / 12 (ÖLÇ, bu listeye güvenme).
  cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report

HAT B — mühendislik: C3 (execution/participant.py adaptörü). Importer-allowlist
  kararı #761'de İMZALANDI (Seçenek A). NEGATİF KONTROL ZORUNLU: sahte bir importer
  containment kapısını gerçekten kırmızıya çevirmeli. ÖNCE KENDİN ÖLÇ.

HER CLAUSE İÇİN PAZARLIKSIZ:
  1. Mevcut testler bu kusur altında YEŞİL mi kalıyor? Kalıyorsa yeni assertion BAŞKA
     bir eksene bakmalı. (ADIM 83 dersi: guard'ı mutasyonun altına taşımak istisnayı
     aynı şekilde fırlatır → pytest.raises tek başına "durum değişmedi"yi kapatmaz.)
  2. İddiayı, karşıtının ÜRETİLEBİLECEĞİ bir dünyada ölç. "Result yok" demek hiç
     backtest admit edilmemişse totolojidir.
  3. Negatif kontrol koş ve KİMİN kırmızıya döndüğünü OKU; yalnız yeni testi düşürmeli.
  4. Koşamadığın bir suite'e (e2e / @a11y — Docker Hub 403) assertion YAZMA.
  5. Kriterin SON clause'u kapanıyorsa debt_class'ı KALDIR.

ORTAM: Postgres KURULABİLİR — pg_ctlcluster 16 main start + entropia rolü/DB.
  Integration suite onsuz SESSİZCE skip eder; pg_isready ile ÖLÇ.
  Alt küme: --no-cov -p no:randomly. Test eklediysen repository_facts'i YENİDEN ÜRET.

DUR koşulları: imzasız kapı, çözülmemiş PO kararı, kırmızı focused test, OpenAPI drift,
çoklu alembic head, historical Result davranışı değişimi.
PR'ı DRAFT aç, durumu dürüstçe yaz, DUR. MERGE ETME.
```
