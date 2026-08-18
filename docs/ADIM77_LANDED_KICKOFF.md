<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular).

# ADIM 77 LANDED — P1 + P4: iki N+1 bacağı batch'lendi (PR #754) · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 77. Bu belge **devam noktasıdır**, kayıt değil.
> **Bu kickoff'u slice'ı yazan oturum yazmadı** — slice ritüelsiz açılmıştı, kaydı dalgayı
> merge eden oturum ürün sahibinin talimatıyla yazdı. Ölçülen ile dalın iddia ettiği
> §ADIM 77 içinde ayrı işaretlidir; buradaki çapalar ağaçtan doğrulanmıştır.

## Neredeyiz

alembic head **`0043_i08_registry_strategy_fks`** (migration yok) · `ENGINE_VERSION`
**değişmedi** · OpenAPI **değişmedi** · golden digest'ler ellenmedi ·
`SHARED_ALLOCATION_STATUS` = **`future_dev`**. **Blocker sayısı DEĞİŞMEDİ (1 — yalnız
A-08), verdict BLOCKED.** Kabul borcu tavanları bu slice'ta **oynamadı**.

Bu, ADIM 74/75/76 ile aynı dalganın **son** PR'ıydı ve dalganın **tek ürün-kodu** slice'ı.
Dalganın diğer üçü: 74 = R2 + R3 kapanışı, 75 = kabul borcu batch 07 (doc 07 frontend),
76 = P-E6/C8 containment kapısının ikinci dünyası.

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

| Sembol | Nerede | Ne için yeniden kullanılır |
|---|---|---|
| `find_approved_tick_revisions_for_instruments` | `infrastructure/postgres/repositories/market_data.py` | çok enstrümanlı onaylı tick revizyonu; `get_dataset_roots`'un alan-alan aynası |
| `get_strategy_revisions` | `infrastructure/postgres/repositories/strategy.py` | çoklu strateji revizyonu (PK batch); `mainboard.get_work_object_revisions`'ın aynası |
| `_mirror_ref` | `application/commands/readiness_check.py` | bir payload'ın doc 02 §7.1 mirror pin'i — "mirror NEDİR" sorusunun **tek** tanımı |
| `_tick_data_demands` | `application/commands/readiness_check.py` | döngüden ayrılmış "tick data isteyen kalemler" + dört bilinçli sessizlik tek yerde |
| `_pinned_mirror_refs` | `application/commands/backtest_run.py` | pinli work-object revizyonlarının taşıdığı mirror ref'leri (döngü ÖNCESİ) |
| `_resolve_strategy_payload(session, payload, mirrors=None)` | `application/commands/readiness_check.py` | opsiyonel önceden-getirilmiş harita; `None` varsayılanı eski çağıranları statement statement korur |
| `test_query_budgets.py::_measure` | `backend/tests/integration/` | iki boyutta statement sayan + slope assert eden bütçe harness'ı |

**Yeni bir batch'li okuyucu yazacaksan üçüncü bir idiom icat etme** — yukarıdaki iki
aynadan birini kopyala: boş girdi round trip'siz kısa devre, tekrarlı id'ler çöker, satırı
olmayan id haritada YOKTUR (çağıranın `is None` dalı değişmez).

## Pazarlıksız — bu slice'ın öğrendikleri

- **Fail-closed bir bacakta FIXTURE ölçümün kendisidir.** Kapıyı açmayan bir fixture hiç
  koşmamış bir bacak için yeşil slope raporlar. Bir sayıya inanmadan önce bacağın
  gerçekten koştuğunu kanıtla (tick bacağında `tick_policy` `require` olmalı; admission
  bacağında HER enstrümanın kendi onaylı revizyonu olmalı, yoksa 422 birinci kalemde durur).
- **"Batch aynı satırı seçer" bir hız iddiası değil, bir GİRDİ iddiasıdır.** Pinlenen
  revizyon değişmez manifest'e girer (doc 15 §15, INF-04/INF-05). Sadece **TOTAL** bir
  sıralamanın üstünde `DISTINCT ON` kullan, ve iddiayı **eşit `created_at`'li** bir
  fixture ile sürdür — ayrı zaman damgalarıyla tie-break hiç koşmaz ve her implementasyon
  geçer. Assertion'ı tekil okuyucuya karşı **oracle** olarak yaz, elle beklenti yazma.
- **Sırası TOTAL olmayan bir bacağı batch'leme.** `_resolve_external` (leg 3) böyledir:
  `work_object_revision_id` UNIQUE değil, per-item kazanan **tanımsız** → hangi satırın
  kazanacağı bir **ürün kararıdır (G15)**, performans değişikliği değil. Bütçe satırı
  bilerek `per_item: 1`.
- **Ratchet AŞAĞI iner.** İki yeni satır `per_item: 0` ile donduruldu; bir bütçeyi veya
  slope'u YÜKSELTMEK gerekçesi yazılmış bilinçli bir düzenlemedir, yeşile ulaşma yolu değil.
- **Identity-map kör noktasını varsayma, ölç.** `query_budgets.json` başlığının anlattığı
  "aynı PK'ye konan `session.get` SQL üretmez" durumu burada geçerli DEĞİLDİ; bilerek
  expunge edilmemiş bir oturumda slope 2 yeniden üretilerek gösterildi.
- **Alt küme koşarken `--no-cov`;** `pytest | tail` KULLANMA (exit code `tail`'in olur);
  tam suite'i tek çağrıda koş ve ortada öldürme.
- **`cancelled` ≠ `failure`.** Bu dalgada iki bağımsız PR (#754 ve #756) aynı arızaya
  çarptı: `npm exec playwright install --with-deps chromium` içinde ~60 dakikalık apt
  asılması, job timeout'unda öldürme, **hiçbir test gövdesi koşmadan**. LOG'a bak; çare rerun.
- **Yeşil exit code kanıt DEĞİLDİR** — Postgres'e ulaşamayan entegrasyon suite'i fail
  değil SKIP eder ve `exit 0` verir. Çıktıda nokta mı `s` mi diye bak.

## Sıradaki tasarım işaretleri

- **Kalan ölçülmüş N+1: leg 3** — yalnız **G15 imzalandıktan sonra** dokunulabilir.
  Brief: `docs/decisions/` (G15 bloğu #747'de indi, **imzasız**).
- **#618 (Approve Package pinned-resolver, 2 round trip/pin)** hâlâ açık ve bu slice'ın
  **kapsamı dışındaydı** — aynı şekil, farklı yüzey; `dependency_pins.ensure_pinned_resolvers_active`
  bütçe satırı onu bekliyor.
- **Kritik yol hâlâ kodda değil imzada:** `C2`/E4b (`settle` + `finalize`, `PHASE_ORDER`'a
  P10, `iter_portfolio`) için `G9` + `G13` **imzalandı** (#753), ama `G10` (Gate 2 — lift
  onayı) **hiç talep edilmedi**, `G11`/`G12`/`G8`/`G14` açık, `participant.py` için
  importer-allowlist genişletmesi **insan incelemesi**.
- **A-08 agent kapatamaz.**

## Çalışma yöntemi (bu dalgada işe yarayan)

- **Numarayı kapanış commit'ini YAZARKEN doğrula, merge'den hemen önce bir kez daha:**
  `git fetch && grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -1`. Bu dalgada **üç PR aynı
  anda ADIM 74 talep etti** ve ikisi taşındı; sonra iki PR aynı anda 75 talep etti.
- **Sıra bir tercih değil, bir KAPI:** `check_classification` canlı kickoff'un ağaçtaki
  **en yüksek numaralı** `ADIM<n>` dosyası olmasını ister (`_check_live_kickoff_is_newest`).
  Yüksek numaralı olan önce inerse, düşük numaralı PR kendi kickoff'unu `current`
  yapamaz ve **ikinci kez** renumber olmak zorunda kalır.
- **main'i içeri alırken REBASE**, sunucu-tarafı "Update branch" butonu **KULLANMA** —
  o merge bu depoda bir `PROJECT_HISTORY.md` kaydını sessizce düşürdü ve hiçbir CI kapısı
  görmedi. Aynı sebeple **auto-merge'ü yalnız dal main ile GÜNCELken arm et**; güncel
  olmayan bir dalda auto-merge sunucu-tarafı güncellemeyi tetikleyebilir.
- **Artefakt çakışmasını YENİDEN ÜRETEREK çöz** (`README.md`,
  `docs/generated/repository_facts.{json,md}`), taraf seçerek değil: `cd backend && uv run
  python ../scripts/generate_repository_facts.py --root ..` — `--root ..` şart.
- **`docs-history-guard` başlık YENİDEN ADLANDIRMASINI kayıt silme sanır.** Renumber
  gerçekten gerekiyorsa önce kaldırılan/eklenen başlıkların **saf bir renumber** olduğunu
  mekanik olarak kanıtla; kapıyı kapatma (`ENTROPIA_HOOKS`'a dokunma).
- **Rebase sonrası `## Stage <n>` bloğu yanlış yuvaya düşer** — artan sıraya geri taşı;
  `CLAUDE.md` zincirinde de yeni slice'ın bloğu "Son dalga", öncekiler "Öncesinde" olur ve
  **hiçbir öncesi düşürülmez**.

## Paste-ready resume prompt

```
Entropia — sıradaki slice. ÖNCE OKU: CLAUDE.md §Session START, docs/ADIM77_LANDED_KICKOFF.md
(bu belge), docs/PROJECT_HISTORY.md §ADIM 77, docs/STAGE_BUILD_PLAN.md.

TABAN: ADIM 77'nin merge edildiği main. SHA'yı doğrula AMA ETİKETE GÜVENME — numarayı
`git fetch && grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -1` ile ÖĞREN. Bu dalgada
ÜÇ PR aynı anda ADIM 74 talep etti, sonra İKİ PR aynı anda 75 talep etti; ikisi de taşındı.

ÖN KOŞUL — ÖLÇEREK SEÇ
  1. Planın "açık" dediği kalem ağaçta KAPALI olabilir; her seferinde `backend/src`'e bak.
  2. Kriterin ya da issue'nun ADLANDIRDIĞI davranış sevk edilmemişse sınıfı yanlıştır.
  3. İmzasız bir kapının arkasındaki slice'a BAŞLAMA; ürün kararı UYDURMA.
     Açık kapılar: G10 (hiç talep edilmedi) · G11 · G12 · G8 · G14 · G15 · G4 · G1/G2/G3.

PERFORMANS İŞİ YAPACAKSAN
  - Önce ÖLÇ, sonra onar; ölçülen slope'u query_budgets.json'a ÖNCE yaz.
  - Fixture'ın bacağı gerçekten koşturduğunu kanıtla (fail-closed / dar kapılı bacaklar
    hiç koşmadan yeşil 0 raporlar).
  - Davranış paritesini maliyetten AYRI kanıtla; negatif kontrolü pristine dosyaya karşı,
    batch'li okuma BAŞINA koş.
  - Sırası TOTAL olmayan bir bacağı batch'leme (leg 3 = G15, ürün kararı).
  - Yeni çoğul okuyucu = mevcut aynanın kopyası; üçüncü idiom yok.

PAZARLIKSIZ
- Ratchet/baseline/golden DÜŞÜRME-YÜKSELTME; coverage tabanına dokunma.
- Tam suite tek `uv run pytest` çağrısı; alt kümede `--no-cov`; `| tail` yok; exit code'u
  AYRI oku. Aynı DB'ye ikinci pytest başlatma.
- Yerel `entropia` veritabanına `alembic upgrade head` koşmadan contract testlerine bakma
  — "relation does not exist" bir ürün hatası değil, migrate edilmemiş bir DB'dir.
- main'i içeri alırken REBASE; "Update branch" butonu YOK; auto-merge'ü yalnız dal
  GÜNCELken arm et.
- Üretilmiş artefaktı elle yazma, YENİDEN ÜRET (`--root ..`).
- strict:true bir MERDİVEN: her merge diğer PR'ların yeşilini bayatlatır. Sıra planla.

Kapanışta CLAUDE.md §Session CLOSING ritüelinin 6 maddesi — ve ritüeli ERTELEME:
bu slice (#754) kaydı ve kickoff'u olmadan PR'a açıldı, ikisini de dalgayı merge eden
oturum yazmak zorunda kaldı. ADIM 69/70 ve 72 aynı borcu daha önce üç kez ödemişti.
```
