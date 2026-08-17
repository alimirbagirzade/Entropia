<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 69 LANDED — kalan V18 closure işi bağımlılık sırasına konuldu (P-D, #728) · sıradaki slice için kickoff

> **NUMARA NOTU — merge sırası TERS.** #728 (`2a314ae`) main'e #729/#730'dan **önce** indi ama
> kaydı yazılmadı; #730 aradan geçip **ADIM 66**'yı merge edilmiş adla aldı. Kapanış PR'ı
> (#732) sıra beklerken **#733 ADIM 67**'yi ve **#736 ADIM 68**'i merge edilmiş adla aldı.
> Numaralar yeniden atanmaz → bu belge **ADIM 69**'dur. Dal (`docs/stage-67-landed`) ve
> commit mesajı ADIM numarası **taşımaz**.

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 69. Bu belge **devam noktasıdır**, kayıt değil.
> Sıralamanın kendisi: `docs/implementation/final_closure_ordered_plan_2026-08-13.md`.

> **BU KICKOFF ADIM 70'İ DE TAŞIR.** Aynı kapanış PR'ında **ADIM 70** (F1, PR #729) geriye
> dönük kaydedildi ve **kendi kickoff'u YOK, bilerek**: geriye dönük bir kayıt, ve #729 sıradaki
> işi değiştirmiyor (o an `P3` + `C1` + `C5`; `C1` bu kapanış sıra beklerken **#735 ile
> indi**, güncel liste yukarıdaki tabloda). Dakikalar önce yazılmış bir kickoff'u aynı
> içerikle çoğaltıp demote etmek çalkantı olurdu. `check_classification` bunu görmez — kural
> numarayı **dosya adından** okur ve bu belge en yeni kickoff **dosyası** olarak kalır.
> **Bir kickoff kaybolmadı; hiç yazılmadı ve nedeni burada.**

## Neredeyiz

**Ürün kodu bu slice'ta değişmedi** (tek satır bile) · migration yok · `ENGINE_VERSION`
değişmedi · OpenAPI değişmedi · **blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

Kalan closure işi artık **19 tek-sorumluluklu slice**: `F1–F3` (financial semantics),
`R1–R4` (research provenance), `P1–P3` (performance), `C1–C9` (shared portfolio). Her slice
on dokuz zorunlu alanı taşıyor.

**W4'ün ilk dalgası indi — bu kapanış yazılırken YENİDEN ÖLÇÜLDÜ.** Kayıt ilk yazıldığında
*"`R1`+`R2` → #730"* diyordu; **yanlıştı**: planın `R1`'i
(`final_closure_ordered_plan_2026-08-13.md:331`) **`TimingProvenance` + byte-identity proof**
olduğu için `R1` = **#734**, #730 ise `P-E3`/bundle kimliğiydi (ayrı slice).

| Slice | Durum |
|---|---|
| `F1` | landed — **#729** (bu kapanışta ADIM 70) |
| `R1` | landed — **#734** |
| `C1` | landed — **#735** (50 golden digest kıpırdamadı) |
| **`P3`** | bu belgenin resume prompt'u — ama **PR #741 olarak AÇILDI**, ikinci kez açma |
| ~~`C5`~~ | **hedefi zaten sevk edilmiş** (aşağıda ölçüldü); kayıt düzeltmesi **#740** |
| `R3` | `R1` indiği için serbest |
| `R2` | **PR #742 olarak açıldı** |
| `R4` | **G6 imzasını** bekler |

> **BU TABLO KAPANIŞ ANINDA ÖLÇÜLDÜ (2026-08-17) ve hızla bayatlıyor.** Bir sonraki oturum
> **önce `git fetch` + açık PR listesi** çeksin: bu kapanış sıra beklerken plandan üç slice
> daha PR'a dönüştü (`P3` #741, `R2` #742, `C5`'in kayıt düzeltmesi #740). Aşağıdaki
> paste-ready prompt `P3` içindir ve **#741 onu zaten talep etmiştir** — prompt'u yöntem
> şablonu olarak kullan, işi ikinci kez açma.

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

| Çapa | Nerede | Ne için |
|---|---|---|
| 19 slice × 19 alan | `final_closure_ordered_plan_2026-08-13.md` §3 | bir slice'a başlarken **kendi satırını oku** — production files / no-touch / stop condition orada |
| `[V-BACKEND]` · `[V-GOLDEN]` makroları | aynı belge §3 başı | doğrulama bloğunu 19 kez kopyalama, adıyla çağır |
| 16 maddelik kapı sicili (G1–G16) | aynı belge §2 | her kapı için **kim açar / neye bakarak / kanıt nerede** |
| Paralellik şeritleri (W4-a … W8) | aynı belge §4.2 | hangi slice'lar aynı dalgada açılabilir |
| Merge ekonomisi aritmetiği | aynı belge §5.1 | tavanı tartışmadan önce oku — sezgi yanlış |
| `_build_stepper` iç fonksiyon haritası | aynı belge §1.2 | `engine.py`'de çakışma sorusu her sorulduğunda **iç** fonksiyona bak, dosyaya değil |

## Pazarlıksız — bu slice'ın öğrendikleri

1. **Bir kabul kapısını SAYIYLA ifade etme.** *"46 golden digest unmoved"* ölçüldüğünde **50**
   çıktı (#720 dört senaryo ekledi), *"37 non-portfolio"* **41** çıktı, *"25 portfolio oracle"*
   **hiçbir okumada** üretilmedi. Kapıya **dosya adı** yaz; sayının üreticisi başka bir slice
   olduğunda sayı sessizce bayatlar. `engine_golden_digests.json`'ın içindeki `engine_version`
   alanı tam olarak bu yüzden var — bump'ı yakalayan **o**.
2. **"Aynı dosyaya dokunuyorlar" bir bağımlılık kanıtı DEĞİLDİR.** `_build_stepper` **tek
   ~2541 satırlık fonksiyon**; E1 ile E4'ün bütün dokunuş noktaları içinde. Çakışma sorusu
   **iç fonksiyon** düzeyinde çözülür: A-2 `_open()`'da, E4a `_phase_carry/_held/_entry`'de →
   **ayrık**; A-3 ile E4a `_phase_tail()`'de → **çakışır**.
3. **Asıl kısıt paylaşılan KABUL ARTEFAKTI olabilir.** `engine_golden_digests.json` bir PR için
   *"byte değişmedi"* kapısı, diğeri için *"yeniden üret"* çıktısı. İki PR ona birden sahip
   olamaz → **karşılıklı dışlama** kenarı, öncelik kenarı değil. Aynısı `docs/openapi.json`,
   `repository_facts.md`, `query_budgets.json` için de geçerli.
4. **`strict: true` altında paralellik CI duvar saatini KISALTMAZ.** ≈ `N × T`; paralellik
   **yazma** eşzamanlılığı satın alır. Tavan: **3 açık PR**, ≤2'si `backend/src`,
   `engine.py`/üretilmiş artefakta dokunan **TAM 1**. Sıra **en çok çakışan ÖNCE** — ağırı sona
   bırakmak ona her küçük merge'de 48–85 dk'yı **ve kendi kabulünü** yeniden ödetir.
5. **`issue CLOSED ≠ çözüldü` harfi harfine uygulanır.** #550/#551/#552 kapalı; **Karar 1
   imzasız** (dört kutu boş, `karar veren:` boş) → `F3` başlayamaz. #550'nin kanonik seçeneği
   ise **issue gövdesinde kayıtlı** ve tahliye edildi (G5) — yani her kapalı issue aynı değil,
   **kanıta bakılır**.
6. **Bir prompt kapanış ritüelini kapsam dışı bırakırsa, borcu AYNI OTURUMDA planla.** P-D'nin
   promptu tek dosyaya kilitliyordu; #728 ritüelsiz indi, araya iki slice girdi, **numara gitti.**
7. **Başkasının slice'ının kaydını yazma.** #729'un ADIM kaydı yok; bu slice **borcun varlığını**
   ölçüp kaydetti (`§ADIM 69` md. 6) ama anlatısını uydurmadı.

## Sıradaki tasarım işaretleri

- **`P3` (önerilen ilk hamle):** `readiness_check.run_readiness_check` için **whole-operation**
  budget satırı + tamamlanmışlık kapısını elle yazılmış kümeden **türetilmiş** kümeye çevir.
  **`per_item` ilk ölçümde 0 OLMAYACAK** (leg 2 ve leg 3 canlı N+1) — **ölçülen** eğimi
  `note` ile yaz; 0 yazmak build'i düşürür, satırı hiç yazmamak ise bu kapının kırmak için
  var olduğu sessizliktir. `P1`/`P2` sonra onu **aşağı** çeker.
- **`C1` (E4a) İNDİ (#735)** — ve **stop condition'ı ateşlendi, cevabı da geldi:**
  `_phase_tail`'in scaling bölümü **describe/book çifti olarak ayrılabiliyor ama stacking
  bölümü book etmeden ÖNCE sıralanamıyor**; paylaşımlı bir run için bu *"ayrılamaz"* ile
  aynı şey → **P-C2 §C.3.8 seçenek (a) artık ÖNERİ DEĞİL, ZORUNLU** (yani `G12`:
  scaling-enabled Strategy'ler paylaşımlı run'da admission'da bloklanır). Ölçüm:
  `docs/audit/closure_c1_phase_tail_scaling_separability_2026-08-17.md`. **`_phase_tail`
  karakter karakter aynı kaldı** — `F3` de onu talep ettiği için C1 bilerek dokunmadı.
  Üç faz `_compute_carry`/`_book_carry`, `_evaluate_held`/`_apply_held`,
  `_evaluate_entry`/`_apply_entry` olarak ayrıldı; kapı tutuldu (**50 digest unmoved**,
  `engine_golden_digests.json` byte değişmemiş).
- **`C5` — HEDEFİ ZATEN SEVK EDİLMİŞ, bu kapanışta ÖLÇÜLDÜ.** Plan `C5`'i *"`_resolve_allocation`
  `config`'i CANLI draft satırlarından kuruyor, `plan_revision_id`'yi çıplak pointer olarak
  yazıyor"* diye tarif ediyor (ADR 0002 §10.2 / R-1). **Ağaçta öyle değil:**
  `readiness_check.py::_resolve_allocation` (`:859-862`) config'i **koşullu** kurar —
  `_pinned_revision` bir revizyon döndürürse `PortfolioAllocationConfigV1.model_validate(
  revision.config)` (**dondurulmuş satır**), yalnız `None` döndürürse draft; ve o durumda
  `plan_revision_id` de `None`, yani ikisi **hiçbir yönde** ayrışamaz. `_pinned_config_hash`
  (`:907`) revizyonun **kendi saklanmış** `config_hash`'ini yeniden hesaplamaya tercih eder.
  **Yani `C5` bir kod slice'ı değil, bir KAYIT düzeltmesidir** — bayat olan ADR §10.2'nin
  present-tense cümlesi. Ölçüm ve dispozisyon: **PR #740**. `C5`'i kod yazmak için AÇMA.
- **`C2` sırada ama İNSAN KAPISINDA:** `G9` (ADR §6/§8 amendment) + `G13` (P10 equity point)
  **imzasız**. #731 bunu ölçtü: `settle`/`finalize` **0 hit**, `PHASE_ORDER` **8 fazlı**
  (P10 yok), `iter_portfolio` **0 hit**.
- **`C3` için planın BİLMEDİĞİ BİR KAPI ölçüldü (#731, blocker 4).** Plan adaptörü
  `execution/` **dışına** koymayı, kapının kırmızıya dönmesini ve allowlist'in **bilinçli
  olarak** genişletilmesini öngörüyordu. Ölçüm daha keskin: Protocol'ün ihtiyaç duyduğu
  **altı tipin altısı da** `_PHASE_LOOP_MODULES` içinde (`ItemBarStream`, `ItemTickView`,
  `ItemIdentity`, `PortfolioSnapshot`, `ItemIntent`, `OpenPosition`) → adaptör nereye
  konursa konsun kapı tepki verir, ve **allowlist kararı bir İNSAN incelemesidir**
  (#731 §7 adım 4), ajan işi değil. **Sicildeki 16 kapıya ek bu 17.'dir** ve `C3`'ün
  önünde durur.
- **Başlamayacaklar:** `F2` (G4 briflenmemiş), `F3` (G1/G2/G3 imzasız — ayrıca `_phase_tail`'i
  talep eder), `C2` (G9 + G13), `C6` (G11 + **G12 artık ölçülmüş-zorunlu**),
  `C9` (22 ön koşul + G8/G10/G14). Ready Check **leg 3** hiç programlanmadı (G15).

## Çalışma yöntemi (bu slice'ta işe yarayan)

- **Tasarım belgesinin sayısını taşıma, yeniden ölç.** Dört sayıdan biri kabul kapısıydı.
- **Grafiği doğrula, kabul etme.** Altı düğümün üçü ölçümle şekil değiştirdi.
- **Bir fonksiyonun sahibini `python3` + `re` ile çöz**, göz kararı yapma — 2541 satırlık bir
  fonksiyonda "yakın/uzak" sezgisi işe yaramaz.
- **Kapanış yazmadan önce numarayı iki kez doğrula:** `git fetch` → `grep '^## ADIM'` → açık PR
  listesi. Bu slice numarayı **iki merge geriden** aldı.

## Paste-ready resume prompt

```
ENTROPIA V18 — P3 (Ready Check whole-operation query budget backstop)
TEK SLICE

ROL: Entropia V18 Principal Engineer. Yalnız bu slice.
[ORTAK SÖZLEŞME bloğunu buraya yapıştır]

TABAN
  Beklenen: ADIM 69+70'in merge edildiği main. FARKLIYSA durma, farkı raporla,
  aşağıdaki her ölçümü yeniden yap.

ÖN KOŞUL — YOK. Bu bir KAPI slice'ıdır; application kodu DEĞİŞMEZ.
  readiness_check.py'yi onarmaya kalkma — bu slice ÖLÇER, TAMİR ETMEZ (o P1/P2).

OKU (bu sırayla)
  docs/implementation/final_closure_ordered_plan_2026-08-13.md  §3 "PACKAGE P" → P3 satırı
  docs/implementation/closure_design_portfolio_performance_2026-08-13.md  §D.2
  docs/performance/README.md  (metodoloji + sabit ortam)

YAPILACAK
  1. docs/performance/query_budgets.json'a TEK satır ekle:
       "readiness_check.run_readiness_check"
       axis = "enabled item in the composition", n_small = 1, n_large = 11
     queries_small / queries_large / per_item ÖLÇÜLEREK doldurulur.
  2. test_query_budgets.py::test_every_registered_surface_has_a_budget içindeki
     ELLE YAZILMIŞ kümeyi TÜRETİLMİŞ hâle getir (_measure çağrı yerlerinden).

PAZARLIKSIZ
  - per_item ilk ölçümde 0 OLMAYACAK (leg 2 + leg 3 canlı N+1). ÖLÇÜLEN değeri yaz ve
    `note`'ta leg 3'ü sebep olarak adlandır. 0 yazmak build'i düşürür; satırı hiç
    yazmamak bu kapının kırmak için var olduğu sessizliktir.
  - RATCHET YALNIZ AŞAĞI İNER. Bir tavanı yükseltmek yazılı gerekçe ister.
  - Sayaçların ÖLÇÜLMÜŞ kör noktası var: aynı session'da bir batch'in ısıttığı PK için
    session.get HİÇ SQL üretmez. query_budgets.json `_comment` bunu beş şekliyle yazar;
    kokuyu kapıya bağlamak (tasarım (c)) BU SLICE'IN İŞİ DEĞİL — adını koy, yapma.
  - Türetilmiş kapı parsing jimnastiği gerektiriyorsa (a)+(b)'yi sevk et, kümeyi bırak,
    NEDENİNİ yaz. Yarım (c) yazma.

DOĞRULA
  cd backend && uv run pytest tests/integration/test_query_budgets.py -q --no-cov
    -> çıktıyı DOSYAYA yaz, $?'i AYRI oku. `| tail` KULLANMA.
  Sonra tam gate: [ORTAK SÖZLEŞME → YEREL DOĞRULAMA]
  Postgres :5432 (entropia/entropia); paralel worktree'de TEST_DATABASE_URL
  (postgresql+asyncpg://).

PARALELLİK
  P3 açıkken P1/P2 AÇMA (aynı JSON satırı, aynı test dosyası).
  C5 ve R3 ile paralel açılabilir (C1 #735 ile İNDİ). Tavan 3 eşzamanlı PR.

DAL: perf/closure-p3-readiness-budget-backstop
commit: perf(closure-p3): <subject>
Draft PR aç. MERGE ETME.

KAPANIŞ: CLAUDE.md §Session CLOSING ritual — altı maddenin HEPSİ.
  Numarayı yazmadan ÖNCE: git fetch && grep '^## ADIM' docs/PROJECT_HISTORY.md
  ve açık PR listesi. Bu slice bu adımı atladığı için numarayı **dört merge** geriden
  aldı (67 yazıldı → #730, #733, #736 araya girdi → 69).
```
