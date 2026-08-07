<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 29 kapanış devri — A-08 kaydı #514'ün kanıtsız kapatılmasıyla uzlaştırıldı

## Nerede duruyoruz

ADIM 28 (#628/#630) A-08 için **iskeleyi** kurdu: seeded stack script'i, boş çalışma
defteri, `@a11y` precheck spec'i, 21 kontrat testi. Denetim **yapılmadı**.

Sonra izleme issue'su **GitHub #514 kanıtsız kapatıldı** — `2026-08-07T03:52:03Z`,
`state_reason: completed`, label `human-only` ("Sadece insan kapatabilir; kanitsiz
kapatma yasak"). Bu, aynı issue'nun **ikinci** kanıtsız kapatılmasıdır; ilki
2026-07-30T19:05:32Z'deydi ve 2026-08-03'te geri alınmıştı. **Bu ikincisi geri
alınmadı.**

Böylece belgeler iki yönden birden yanlış hale geldi:

* *"A-08 açık issue #514'te izleniyor"* → **BAYAT** (issue kapalı),
* *"A-08 tamamlandı"* → **YANLIŞ** (defter boş, dört çıkış kriteri de ☐).

**ADIM 29 bu ayrışmayı ÇÖZMEDİ — KAYDETTİ.** Çözüm insana düşer.

## Bu slice ne yaptı (docs-only; ürün kodu, test, CI davranışı değişmedi)

**Kanonik kayıt tek yerde:** `docs/audit/a11y_screen_reader_audit_results.md`
§STATUS ▸ *Tracking-issue state — closure/evidence divergence*. Diğer tüm belgeler
oraya **işaret eder**, olguyu tekrarlamaz.

O blok üç şeyi sabitler:

1. **Beş olgu + nasıl yeniden türetileceği** (`gh issue view 514 --json …`): issue
   durumu, label, denetim yapıldı mı, çıkış kriterleri, kayıtlı bulgu.
2. **Kapalı issue tamamlanma kanıtı değildir** — hüküm cümlesi.
3. **Açık duran iki insan yolu**, ikisi de agent'a kapalı:

   | Okuma | Anlamı | Gerektirdiği insan işi |
   |---|---|---|
   | **(A)** Bilinçli kabul | PO denetimsiz sevkiyatı bilerek kabul etti | D-10 biçiminde **imzalı kalıcı sapma**: adı verilmiş imzalayan + ISO tarih + kapsam. **İmzalayan verilmedi → böyle bir kayıt YAZILMADI.** |
   | **(B)** Sehven kapandı | İzleme yanlışlıkla kapatıldı | Bir **insan** #514'ü yeniden açar. |

   Hiçbiri A-08'i tamamlanmış yapmaz: (A)'da kabul edilen şey denetimin
   **yokluğudur**, (B)'de iş zaten açıktır.

**Dokunulan belgeler (7 + 1 script mesajı):**

| Dosya | Ne değişti |
|---|---|
| `docs/audit/a11y_screen_reader_audit_results.md` | §STATUS'a **kanonik ayrışma bloğu**; §5'e "issue'yu kapatmak dört kriterden hiçbirini karşılamaz" |
| `docs/implementation/a11y_screen_reader_audit_checklist.md` | başlık banner'ına kapatma olgusu; §Çıkış kriteri'ne "iki kez kapatıldı" notu; denetçi satırı ("artık hiçbir açık kayıt bu atamayı izlemiyor") |
| `docs/implementation/v18_final_acceptance.md` | §6'daki 2026-08-03 bloğu **korundu**, altına `GÜNCELLEME (2026-08-07)` eklendi |
| `docs/implementation/entropia_v18_remediation_status.md` | aynı desen + `## Change log`'a 2026-08-07 girdisi + "hâlâ açıktır (GitHub #514)" parantezi düzeltildi |
| `docs/implementation/v18_visual_traceability.md` | Bucket 2'deki A-08 satırı → **"iş AÇIK, izleme KAPALI"** |
| `docs/audit/current_main_ground_truth_2026-08-03.md` | §16 / §17 / §18 / **E-01** satırına tarihli ekler — 2026-08-03 bulguları **aynen duruyor** |
| `CLAUDE.md` | §Current position "Son dalga" + §Açık iş bloğu |
| `scripts/generate_repository_facts.py` | `A08_COMPLETE` kuralının **mesaj metni** ("GH #514 tracks it" artık yanlıştı). Regex ve kural kimliği **değişmedi** → kapı davranışı birebir aynı. |

## Tavizsiz çizgiler (bu slice'ta korundu — bozma)

* Hiçbir belge A-08'i `Complete`/`PASS`/`Done` göstermiyor.
* *"An empty template is not evidence"* worksheet'te **duruyor** (kontrat testi pinliyor).
* **D-10 sürüyor:** WCAG 2.2 AA **1.4.3 karşılanmıyor**, AA uyumluluk iddiası yok.
* Tarihsel kayıt **silinmedi**: 2026-07-30 kanıtsız kapatma ve 2026-08-03 yeniden açma
  duruyor; üzerine 2026-08-07 olayı eklendi.
* Otomatik çıktı (axe / keyboard / prechecks) ekran-okuyucu kanıtı **sayılmıyor**.
* **#514'ün durumu DEĞİŞTİRİLMEDİ** — agent açamaz da kapatamaz da.

## Reuse anchor'ları (tam sembol adları)

| Anchor | Nerede |
|---|---|
| `test_human_blocked_banner_stands_while_the_audit_is_incomplete` | `backend/tests/contract/test_a11y_audit_prep_contract.py:262` — sayaçlar eksikken worksheet `A-08 HUMAN-BLOCKED` **ve** `#514` içermeli |
| `test_checklist_still_records_the_audit_as_not_performed` | aynı dosya `:376` — checklist `Denetim yapılmamıştır` + `#514` içermeli |
| `test_worksheet_refuses_automated_output_as_evidence` | aynı dosya — `An empty template is not evidence` literali |
| `INVARIANT_RULES` ▸ `A08_COMPLETE` | `scripts/generate_repository_facts.py:673` — regex `A-08[^\n]{0,80}?(Complete\|PASS\|Done\|tamamlan\|kapandı)`; `NEGATION_RE` (`:661`) olumsuzlanmış satırı muaf tutar |
| `check_classification` | `scripts/generate_repository_facts.py:587` — **tek** `doc-status: current` kuralı; bu dosya `current`, ADIM 28 `historical`'a çevrildi |
| `ALWAYS_HISTORICAL_GLOBS` | `:551` — `docs/audit/*.md` daima `historical`; worksheet'in banner'ı bunu açıklıyor |

## Açık sınırlar (dürüst)

* **A-08 denetimi YAPILMADI.** Defter boş, 4/4 ☐, findings register'da tek kayıt yok.
* **İzleme kapalı.** #514 kapalı; iş açık, izleme kapalı. Çözüm insana düşer (A veya B).
* **K-2..K-6 ölçüldü, düzeltilmedi** — her biri ayrı ürün kararı (skip link, `contentinfo`,
  `/user-manual` `<h1>`, 21 rotada `h1→h3` atlaması, odak göstergesi).
* **D-10** imzalı kalıcı sapma sürüyor.
* **Alertmanager YOK** — ADIM 25/26 kuralları ateşliyor ama kimseye ulaşmıyor.
* **ADIM 23 ve ADIM 24 `PROJECT_HISTORY.md`'de hâlâ KAYITSIZ.**
* **Memory checkpoint (kapanış ritüeli md. 4) YİNE YAPILAMADI** — ne ecc knowledge graph
  MCP'si ne `claude-mem` bu oturumda bağlıydı. Bağlandığında geriye dönük yazılabilir:
  entity `Entropia ADIM 29 — A-08 record reconciliation`, ilişki `unblocks` → PR B.

## Sıradaki iş — DEĞİŞMEDİ

**PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.**

---

## Paste-ready resume prompt

```
ENTROPIA V18 — PR B: ItemParticipant adaptörü + backtest_engine call site

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT — özete güvenme):
  git fetch --all --prune && git log --oneline origin/main -6
  gh pr list --state all --limit 8
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check

OKUMA SIRASI
1. docs/ADIM29_LANDED_KICKOFF.md (bu dosya — son kapanış devri)
2. docs/STAGE2_HANDOFF.md §"... landed" + §Next
3. docs/CODEMAPS/JOBS_AND_EVENTS.md + BACKEND_LAYERS.md
4. Kod okumadan önce codebase-memory-mcp (search_graph / trace_path /
   get_code_snippet) — kör grep + tam dosya okuma yok.

İŞ
PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.
`run_portfolio` üretimde çağrısız; `:363` `combine_item_runs`;
`SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI). ADIM 20
matrisindeki A1/A3/A5 dışında hiçbir satır bu boşluk kapanmadan kapanamaz.
Stepper #602'de indi; kalan borç adaptör + call site.

KURALLAR
- Direct-author (Workflow YOK); önceki slice'ın desenini aynala: module-level
  async command, one-tx no-commit, `run_idempotent`,
  `session.refresh(with_for_update=True)`, `_audit_and_outbox`.
- Tembel merdiven (ponytail-entropia): gerekiyor mu → codebase'de var mı →
  stdlib → kurulu bağımlılık. Coverage kapısı ve katman deseni pazarlıksız.
- Yerel doğrulama: cd backend && uv run ruff check . && uv run ruff format
  --check . && uv run mypy src && uv run pytest -q  (kapı %90)
  + yeni her `create_*` için L1 FK insert-order kanıtı + alembic up/down/up.
- Kod-review CRITICAL/HIGH bulgularını DÜZELTMEDEN ÖNCE empirik doğrula.
- GateGuard: YENİ dosyayı Bash heredoc ile yaz; mevcut dosyada Edit fact-force
  tetikler (4 olgu sun, tekrar dene).
- Yeni belge yazarken: tek `doc-status: current` kuralı geçerli; sayı yazma,
  docs/generated/repository_facts.md'ye referans ver.
- A-08 YAPILMADI ve #514 KANITSIZ KAPATILDI (2026-08-07, ikinci kez). Hiçbir
  belgeye A-08 için `Complete`/`PASS`/`Done` YAZMA; "açık issue #514'te
  izleniyor" da YAZMA — ikisi de yanlış. Kanonik kayıt:
  docs/audit/a11y_screen_reader_audit_results.md §STATUS ▸ Tracking-issue state.
  #514'ün durumunu DEĞİŞTİRME — agent açamaz da kapatamaz da.
- Başarısız test varken `Complete` yazma.

KAPANIŞTA
CLAUDE.md §Session CLOSING ritüelinin 6 maddesi + kapanış PR'ında:
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
  git diff origin/main -- docs/ | grep '^-## '   → BOŞ olmalı
```
