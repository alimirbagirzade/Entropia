# Paylaşımlı koşuda ertelenen fill / bekleyen limit (P2): admission'da **blokla** mı, P2'yi **modelle** mi? (kapı **G11**)

> **BU BELGEDE HİÇBİR KARAR VERİLMEMİŞTİR.** Yazarın rolü **hazırlık**tır. §Karar'ın
> imza bloğu **boştur** ve onu yalnız ürün sahibi / maintainer doldurabilir.
> `closure_g4_cap_overflow_2026-08-17.md`, `closure_g15_external_row_winner_2026-08-17.md` ve
> `closure_participant_importer_allowlist_2026-08-18.md` ile aynı disiplin.
>
> **GÜNCELLEME (2026-08-26): §Karar İMZALANDI — (a) tam admission blok (entry + exit).**
> Yukarıdaki cümle belgenin yazıldığı anı anlatır ve tarihsel olarak doğrudur; imza
> §Karar'daki kutulardadır. Ön koşul kutusu `sayılamadı` işaretlenmiş ve belgenin kendi
> *"(a) bu sayı alınmadan imzalanmamalıdır"* kuralı ürün sahibi tarafından **bilinçli olarak
> geçersiz kılınmıştır** — gerekçe imza notundadır. Uygulama bu belgeye değil `C6`'ya aittir
> (§Sınırlar md. 5, değişmedi).

- **Tarih:** 2026-08-18
- **Base:** `origin/main` @ `fbb45e1` (`test(closure-e6): exercise the containment gate in both values of the flag (#756)`)
- **Kapsam:** paylaşımlı (shared capital) koşuda **P2** — ertelenmiş fill'ler ve bekleyen
  (resting) limit/stop emirleri. **Yalnız** bu faz.
- **Bloklar:** `C6` (admission blocker'ları). Plan §6 `C6` satırı: `C4 + G11 + G12`.
- **BLOKLAMAZ:** `C2` (#759), `C3` (E4c — ayrı ön koşulu #761 ile imzalandı), `C4`, ADR §16
  Gate 2, `G12`, A-08.
- **Neden şimdi:** `G11`, kapanış programının **brief edilmemiş son kapısıydı**. `G4` (#755),
  `G15` (#747), `G12` (#752) ve participant importer allowlist'i (#761) imzalanacak bir yere
  kavuştu; `G11`'in imzalanacak bir yeri **yoktu**. Bu belge o yeri açar, kararı vermez.

---

## Taban notu (dürüstlük)

**`C2` bu belge yazılırken main'de DEĞİLDİ** (#759 açık; `Backend` job'ı koşuyordu, diğer 21
check yeşildi). Bu belgenin **hiçbir ölçümü** #759'un dalına dayanmaz — hepsi `fbb45e1`
üzerinde, sevk edilmiş kod üzerinde yapıldı. `PHASE_ORDER`'ın bugünkü değeri de o tabandan
okundu ve **sekiz fazdır** (P10 henüz yok).

`G11` `C6`'yı bloklar; `C6` `C4`'ü, `C4` `C3`'ü, `C3` `C2`'yi bekler. Yani bu kapı **bugün
kritik yolda değildir** — ama `C9` (lift) öncesinde imzalanmak zorundadır ve karar
verilmediği sürece §Ölçüm 2'nin asimetrisi yüzünden **kendiliğinden bir varsayılana
düşemez**. Bu belge o yüzden erken yazıldı, acil olduğu için değil.

Satır numarası bilerek yazılmamıştır (CLAUDE.md §Conventions: sembol adı yaz).

---

## Ölçüm 1 — P2 kanonda **ledger yazan** bir fazdır, ama `PHASE_ORDER`'da **yoktur**

ADR-0002 §8.2 faz tablosu:

| # | Faz | Kapsam | Ledger yazar mı? |
|---|---|---|---|
| P2 | *Resolve open orders and previously scheduled fills* | per item | **evet** |

Sevk edilen `portfolio_engine.py::PHASE_ORDER` (`fbb45e1`):

```
("P1", "P3", "PV", "P4", "P5", "P6b", "P7", "P9")
```

G9 amendment'ı (ADR §13.2) buna `P10` ekler. **P2 hiçbir sürümde yoktur.** Yani paylaşımlı
faz döngüsü, kanonun *ledger yazan* olarak işaretlediği bir fazı hiç çalıştırmaz.

## Ölçüm 2 — ASİMETRİ: P8 **reddedilebilir**, P2 **reddedilemez**. Kapı bu yüzden admission'da olmak zorunda

`portfolio_engine.py` modül docstring'inin honest boundary md. 2'si **P0 / P2 / P8**'i
*birlikte* "modellenmiyor" diye anar. Ama sevk edilen **refüz yalnız P8'i kapsar**:

```
if decision.kind != "entry":
    raise UnsupportedIntentKindError(...)   # "apply phase is P8 (same-direction scaling)"
```

`backend/src` genelinde P2 için **hiçbir refüz yoktur** (ölçüldü: `UnsupportedIntentKindError`
tek çağrı yeri, o da `kind` üzerinde).

**Bu bir eksiklik değil, yapısal bir farktır ve kararın çerçevesini belirler:**

- **P8 kendini arbitrasyon sınırında ilan eder.** Bir scaling niyeti `decision.kind` olarak
  P7'ye ulaşır; orada bakılacak bir alan vardır, dolayısıyla fail-closed refüz **mümkündür**.
- **P2 hiçbir şey ilan etmez.** Ertelenmiş fill bir *intent kind* değildir; item'ın kendi
  execution modelinin bir **zamanlamasıdır** ve booking, katılımcı herhangi bir niyet
  önermeden önce olur (§Ölçüm 4). Bakılacak bir alan **yoktur**.

**Sonuç:** P8 için "runtime'da reddet" gerçek bir seçenekti. P2 için **değildir** — koşu
başladıktan sonra reddedilecek bir an yoktur. Bu yüzden §Seçenekler'in (a) kolu *admission*
kolu olarak yazılmıştır; "P7'de reddet" diye bir üçüncü yol **ölçülerek elendi**.

## Ölçüm 3 — erteleyen timing kümesi **tam olarak üçtür**

`execution/fills.py::_fill_schedule` haritası:

| `entry_timing` / `exit_timing` | schedule | erteler mi? |
|---|---|---|
| `next_candle_open` | `next_open` | **evet** |
| `next_candle_close` | `next_close` | **evet** |
| `intrabar_touch` | `touch` | **evet** (bekleyen touch emri) |
| `current_candle_close` | `immediate` | hayır |
| `market_fill_simulation` | `immediate` | hayır |
| `limit_fill_simulation` | `immediate` | hayır (fill'i limit makinesi yönetir) |
| `stop_limit_priority_simulation` | `immediate` | hayır |

Buna **emir tipi** ekseni eklenir: `order_config.type` `limit_order` / `stop_limit_order`
ise bekleyen bir emir vardır (`working_limit` / `working_stop`) ve o da P2'dir — timing
`immediate` olsa bile. Yani kapının ölçeceği yüzey **iki alandır**, biri değil.

## Ölçüm 4 — P2 **İKİ** fazda book eder; P-C2 §C.3.7 bunlardan **birini atlamış**

P-C2 §C.3.7 yalnız `_phase_open_fills`'i adlandırır. Ağaç üzerinde ölçüldü — `_Ledger`'ın
`deferred_entry_fills` / `deferred_exit_fills` sayaçlarını **iki ayrı faz** artırır:

| Faz | Adım | Ne book eder |
|---|---|---|
| `engine.py::_phase_open_fills` | (3) | `next_candle_open` ertelemesi → `_do_open` / `_close` |
| `engine.py::_phase_open_fills` | (3b)/(3c) | bekleyen limit entry; `convert_to_market_order` ile süre dolunca da `_do_open` |
| **`engine.py::_phase_tail`** | **(3d)** | **`next_candle_close` ertelemesi → `_do_open` / `_close`** |

`_step`'in sevk edilen sırası:

```
_phase_admit → _phase_carry → _phase_open_fills → _phase_held → _phase_entry → _phase_tail
```

**İki sonuç:**

1. `_phase_open_fills`, `_phase_entry`'den **ÖNCE** koşar. Yani paylaşımlı yolda ertelenmiş
   bir entry fill, katılımcı hiçbir niyet önermeden ve `PortfolioSnapshot` yayımlanmadan
   pozisyon açar — *arbitre edilmemiş sermaye taahhüdü*. P-C2'nin tespiti sevk edilen faz
   sırasıyla **doğrulandı**.
2. **P-C2'nin "adaptör `open_fills`'i çağırmasın" çaresi tek başına YETMEZ.** `next_candle_close`
   ertelemesi `_phase_tail`'in içindedir ve o faz başka nedenlerle (P8, stacking, bar sonu
   snapshot) çağrılmak zorundadır.

> Bu, tasarım belgesinin bir ölçümünü **düzeltir**. §C.3.7 doğru tehlikeyi doğru sebeple
> tarif ediyor, ama yüzeyi eksik sayıyor.

## Ölçüm 5 — `G11` ile `G12` **aynı fonksiyonda** buluşur, ve o fonksiyon ayrılamaz ölçüldü

`_phase_tail` hem (3d)'yi (P2) hem scale ladder'ı (P8) taşır. ADIM 71 (`C1` / E4a) scaling
bölümünün **describe/book olarak ayrılabildiğini ama book etmeden sıralanamadığını** ölçtü
(guard `position` + `led.trades` okur, stacking ikisini de yazar) → `G12` bu yüzden "öneri"
değil **ölçülmüş zorunluluk** olarak kayıtlıdır (`docs/audit/closure_c1_phase_tail_scaling_separability_2026-08-17.md`).

**Kararın maliyetine etkisi, iki yönde ve ters işaretli:**

- **(a) admission'da bloklamak `_phase_tail`'e HİÇ dokunmaz** — böyle bir Strategy adaptöre
  ulaşmaz, dolayısıyla (3d) hiç tetiklenmez. `G11`'in maliyeti `G12`'nin ayrılamazlığından
  **bağımsız** kalır.
- **(b) P2'yi modellemek `_phase_tail`'i ayırmayı GEREKTİRİR** ve o ayrımın zorluğu ADIM 71'de
  zaten ölçülmüştür. Yani (b), `G12`'nin ölçülmüş zorluğunu **miras alır**.

Bu, iki kapının bağımsız sanılmasını engelleyen bir olgudur; plan §2 onları ayrı satırlarda
listeler ve aralarındaki bu bağı **yazmaz**.

## Ölçüm 6 — açılış yolu ile kapanış yolu **aynı tehlike değildir**

`_phase_open_fills` ve `_phase_tail` (3d) hem entry hem exit erteler:

- **Entry tarafı** (`_do_open`, ve `convert_to_market_order` yolu): **sermaye taahhüt eder**.
  Arbitre edilmemiş bir pozisyon açar — §Ölçüm 4'ün adlandırdığı tehlike **tam olarak budur**.
- **Exit tarafı** (`_close`, kısmî kapanışta `_apply_partial_aftermath`): **sermaye serbest
  bırakır**. Arbitrasyonu baypas etmez; pool'un havuzuna geri koyar.

**Bu bir alt-karar doğurur ve BU BELGE ONU KARARA BAĞLAMAZ.** Exit tarafını da bloklamanın
savunulabilir bir gerekçesi vardır: ertelenmiş bir exit, pozisyonu `PV` anına kadar **açık**
tutar, yani `E(t)` snapshot'ı item'ın kendi execution modeline göre hâlâ açık olan bir
pozisyonu içerir. Bunun bir **kusur** mu yoksa **doğru davranış** mı olduğu bir ürün
sorusudur — item'ın modeline göre pozisyon gerçekten o anda açıktır. §Karar'da ayrı kutu var.

## Ölçüm 7 — bugün bu ekseni tutan **hiçbir kapı yok**

- `execution/fills.py::execution_timing_is_modelled` yalnız **modellenmemiş** timing'i
  bloklar (`STRATEGY_EXECUTION_TIMING_UNSUPPORTED`). `next_candle_open` ve `next_candle_close`
  `_ENTRY_TIMING_MODELLED` / `_EXIT_TIMING_MODELLED` içindedir → **geçer**.
- `domain/readiness/`, `domain/allocation/` ve `application/commands/backtest_run.py`
  içinde shared-mode farkındalıklı **hiçbir** timing/emir-tipi kontrolü yoktur (ölçüldü: 0 hit).
- Bugün hiçbir paylaşımlı koşu P2'ye **ulaşmaz** — ama sebebi bu eksen değil,
  `SHARED_ALLOCATION_STATUS = "future_dev"`'in fail-closed admission guard'ıdır
  (`backtest_run.py`, `allocation/capability.py::shared_allocation_requested`).

> **Dolayısıyla: karar verilmezse "sessizce geçir" kendiliğinden yürürlüğe girmez —
> `C9` (lift) anında girer.** Bu, kapının `C9`'dan önce imzalanması gerektiğinin sebebidir;
> `C6`'yı bloklaması ayrı ve daha erken bir kısıttır.

## Ölçüm 8 — patlama yarıçapı: **VEKİL sayı, üretim DB'si DEĞİL**

Üretim veritabanına erişim yok. Yazılı `entry_timing` / `exit_timing` **değer literalleri**
sayıldı — bu bir **alt sınır vekilidir**, kayıtlı Strategy revizyonlarının dağılımı
**değildir**. Sayılan literallerin **tamamı `backend/`** altındadır (fixture / seed / test);
`frontend/src` bu adları 16 kez anar ama **hiçbiri yapılandırılmış bir değer değildir** —
seçenek listesi ve form alanıdır, o yüzden sayıya girmez:

| Eksen | Erteleyen | Toplam | — |
|---|---|---|---|
| `entry_timing` | `next_candle_open` 19 + `next_candle_close` 3 + `intrabar_touch` 10 = **32** | 65 | ~%49 |
| `exit_timing` | `next_candle_open` 9 + `next_candle_close` 8 + `intrabar_touch` 2 = **19** | 51 | ~%37 |

`next_candle_open`, `ExecutionTimingEnum`'un ilk üyesi ve lookahead'siz kanonik seçimdir;
`ExecutionModel` alanları **zorunludur** (`Field(...)`), yani sessiz bir varsayılan yoktur —
her kayıtlı Strategy bu değeri **bilerek** taşır.

**Üretimdeki sayı §Karar'da bir kutudur ve (a) ailesi o sayı alınmadan imzalanmamalıdır.**
Vekil sayı bile (a)'nın *gerçek bir özelliği kapattığını* gösteriyor: bu ucuz bir blok değil.

## Ölçüm 9 — gözlemlenebilirlik **zaten sevk edilmiş**

`execution/state.py::_Ledger` `deferred_entry_fills` ve `deferred_exit_fills` sayaçlarını
taşır; `execution/output.py` bunları çıktıya, `execution/portfolio.py` composite projeksiyona
yayımlar. Yani hangi seçenek imzalanırsa imzalansın, **yeni bir telemetri altyapısı
gerekmiyor** — sayaçlar yerinde.

---

## Seçenekler

### (a) Admission'da blokla — erteleyen timing / bekleyen emir paylaşımlı modda blocker

`SHARED_ALLOCATION_*` ailesinin emsalinde yeni bir readiness blocker: kod + `message` +
`remediation` + `field_path` (doc 14 §9.1). Kapı Ready Check'te bildirilir **ve**
`backtest_run.py`'ın admission guard'ında fail-closed tekrarlanır (bayat readiness state
geçmesin — `shared_allocation_requested` emsali).

- **Ne korur:** fail-closed. Arbitre edilmemiş sermaye taahhüdü **yapı gereği** imkânsız
  olur. OD-6(a)'nın şekliyle tutarlı. `_phase_tail`'e dokunmaz (§Ölçüm 5).
- **Ne maliyeti var:** paylaşımlı koşularda **gerçek bir özellik** kapanır — vekil ölçüme
  göre yapılandırmaların yarısına yakını (§Ölçüm 8). Kullanıcı Strategy'sini değiştirmeden
  paylaşımlı moda giremez.
- **Not:** bu, timing'i *sessizce* `immediate`'a düşürmekten farklıdır ve o düşürme
  **seçenek olarak bile listelenmemiştir** — `fills.py`'ın "never silently downgraded to a
  fill model it did not request" kuralını doğrudan çiğnerdi.

### (a-dar) Yalnız **entry** tarafını blokla

§Ölçüm 6'ya dayanır: arbitrasyon baypası yalnız açılış yollarındadır.

- **Ne korur:** aynı fail-closed garantisi (taahhüt yolu kapalı), **yarı maliyetle**.
- **Ne maliyeti var:** ertelenmiş exit `PV`'ye kadar pozisyonu açık tutar; `E(t)`'nin bunu
  içermesi doğru mu, kabul edilmiş bir sapma mı — **bu belgede karara bağlanmadı**.
- **Not:** `intrabar_touch` ve bekleyen limit/stop **entry** tarafında olduğu için bu kolun
  altında da bloklanır; sadeleşme `next_candle_*` exit'lerindedir.

### (b) P2'yi modelle — pre-`PV` faz

`PHASE_ORDER`'a P2 eklenir, ertelenmiş fill'ler paylaşımlı ledger'a book edilir, kendi oracle
seti yazılır.

- **Ne korur:** doğru son durum; hiçbir özellik kapanmaz.
- **Ne maliyeti var:** yeni faz + yeni intent kind + oracle seti; **ve** §Ölçüm 5 gereği
  `_phase_tail`'in (3d) bölümünü ayırmayı gerektirir, ki o fonksiyonun ayrılabilirliği
  ADIM 71'de **sınırlı** ölçüldü. `C6`'nın kapsamını belirgin biçimde büyütür.
- **Not:** P-C2 bunu "correct end-state" olarak adlandırır ve **V1 için önermez**.

### (c) Sessizce geçir — mevcut kodun lift anındaki davranışı

Hiçbir kapı eklenmez; `C9` sonrası ertelenmiş fill'ler arbitrasyonu baypas ederek book eder.

- **Ne korur:** hiçbir şey. Listelenmesinin tek sebebi, **karar verilmezse `C9`'da fiilen
  bunun yürürlüğe girmesidir** (§Ölçüm 7) — yani (c) "hiçbir şey yapmama"nın adıdır, ayrı
  bir tasarım değil.
- **Ne maliyeti var:** çalışma standardının yasakladığı sessiz bozulma şekli. İmzalanacaksa
  **imzalı sapma** olarak imzalanmalı, sessizce miras alınmamalı.

---

## Karar — Paylaşımlı koşuda P2 dispozisyonu (G11)

**Ön koşul — patlama yarıçapı (üretim DB'si):** kayıtlı ve `active` Strategy revizyonlarından
kaçı erteleyen bir `entry_timing`/`exit_timing` ya da bekleyen bir emir tipi taşıyor?

`[ ] sayıldı ve 0`   `[ ] sayıldı ve > 0 (sayı: ____)`   `[x] sayılamadı`

> **(a) ve (a-dar) bu sayı alınmadan imzalanmamalıdır.** §Ölçüm 8'in sayısı repo
> fixture'larının vekilidir, üretim dağılımı **değildir**.

> **İmza notu (2026-08-26): yukarıdaki kural ürün sahibi tarafından BİLİNÇLİ OLARAK
> geçersiz kılındı.** Üretim veritabanına erişim yok ve ürün henüz üretimde değil — ölçülecek
> gerçek bir kullanıcı dağılımı mevcut değil. Karar, §Ölçüm 8'in vekil sayısının (a)'nın
> *gerçek bir özelliği kapattığını* gösterdiği **bilinerek** verildi; bu bir gözden kaçırma
> değil, imzalı bir sapmadır.

**Dispozisyon:**

`[x] (a) admission blocker — entry ve exit, erteleyen timing + bekleyen emir tipi`
`[ ] (a-dar) admission blocker — YALNIZ entry tarafı`
`[ ] (b) P2'yi modelle (C6'nın kapsamı büyür)`
`[ ] (c) imzalı sapma — sessiz baypas kabul edilir`
`[ ] (başka: ______________________)`

**Alt-karar — yalnız (a) veya (a-dar) imzalanırsa:** blocker kodu doc 14 §9.1 taksonomisinde
hangi adı alır?
`[x] ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED`
`[ ] STRATEGY_EXECUTION_TIMING_UNSUPPORTED_IN_SHARED_MODE`
`[ ] (başka: ______________________)`

**Alt-karar — `field_path` neyi gösterir?**
`[ ] ihlal eden alanın kendisi (execution.entry_timing / execution.exit_timing / order_config.type)`
`[ ] Portfolio toggle (enabled) — SHARED_ALLOCATION_FIELD_PATH emsali`
`[x] ikisi de (lider blocker alanı gösterir, details tümünü taşır — O-02 emsali)`

**Alt-karar — (a-dar) imzalanırsa:** ertelenmiş bir exit yüzünden `PV` anında hâlâ açık olan
pozisyonun `E(t)`'ye dahil olması kabul ediliyor mu?
`[ ] evet, doğru davranış (item'ın modeline göre pozisyon gerçekten açık)`
`[ ] hayır, ayrı bir kusur olarak izlensin (issue açılsın)`
*(boş bırakıldı — (a) imzalandığı için bu kutu konu dışıdır: exit tarafı da bloklanır)*

**Hüküm onayı (a)** — *P2 runtime'da reddedilemez, çünkü kendini bir `kind` olarak ilan
etmez; P8'in `UnsupportedIntentKindError` emsali P2 için **yapısal olarak** kurulamaz
(§Ölçüm 2)* — kabul ediliyor mu? `[x] evet` `[ ] hayır (gerekçe: ______)`

**Hüküm onayı (b)** — *P2 iki fazda book eder (`_phase_open_fills` **ve** `_phase_tail` (3d)),
dolayısıyla P-C2 §C.3.7'nin "adaptör `open_fills`'i çağırmasın" çaresi tek başına eksiktir
(§Ölçüm 4)* — kabul ediliyor mu? `[x] evet` `[ ] hayır (gerekçe: ______)`

**Hüküm onayı (c)** — *(b) seçeneği `_phase_tail`'in ayrılmasını gerektirir ve o
ayrılabilirlik ADIM 71'de sınırlı ölçülmüştür; yani `G11` ile `G12` bağımsız kapılar
değildir (§Ölçüm 5)* — kabul ediliyor mu? `[x] evet` `[ ] hayır (gerekçe: ______)`

karar veren: **ürün sahibi (alimirbagirzade)**  tarih: **2026-08-26**

---

## Karar ne verilirse verilsin geçerli olan sınırlar

1. **`SHARED_ALLOCATION_STATUS` `future_dev` kalır.** Bu karar containment'ı **kaldırmaz**;
   ADR §16 **Gate 2** (`G10`) ayrıdır ve **talep edilmemiştir**.
2. **`ENGINE_VERSION` bump yok, migration yok, OpenAPI değişikliği yok** — hiçbir seçenek
   bağımsız modun (independent mode) davranışını değiştirmez. Tek-item `run_engine`'in
   P2 davranışı **her seçenekte aynen korunur** (P-C2 §C.4, pazarlıksız).
3. **Sessiz downgrade hiçbir seçenekte kabul edilmez.** Erteleyen bir timing'i paylaşımlı
   modda `immediate`'a düşürmek `fills.py`'ın *"never silently downgraded to a fill model it
   did not request"* kuralını çiğner; bu yüzden seçenek olarak **listelenmemiştir**.
4. **(a) / (a-dar) uygulanırsa negatif kontrol zorunludur:** erteleyen timing taşıyan bir
   Strategy'yle paylaşımlı bir koşu **gerçekten** reddedilmeli, ve blocker kaldırıldığında
   test **kırmızıya dönmelidir**. Bağımsız modun aynı Strategy ile koşmaya **devam ettiği**
   de ayrıca assert edilmelidir — aksi halde blok, kapatması gerekenden fazlasını kapatır.
5. **Uygulama `C6`'ya aittir, bu belgeye değil.** Bugün kod yazmak, negatif kontrolü test
   edecek bir çağıran (`C4`'ün worker kolu) olmadan bir kapı eklemek olurdu.

---

## Bu belgenin kapsamadıkları (dürüst sınır)

- **Üretim dağılımı ölçülmedi.** §Ölçüm 8 repo vekilidir; DB sayımı §Karar'da kutudur.
- **`G12` (P8 / scaling) karara bağlanmadı.** §Ölçüm 5 yalnız iki kapının **bağını** ölçer;
  `G12`'nin kendi imza bloğu `closure_product_decisions_2026-08-13.md` §Karar 6'dadır ve
  **boştur**.
- **OD-2 (mark policy) açık kalır.** Ertelenmiş fill'in fiyatlandığı an ile `E(t)`'nin
  realized-only tanımı arasındaki ilişki bu belgenin konusu değildir.
- **Hiçbir test yazılmadı, hiçbir ürün satırı değişmedi.** Bu belge yalnız `docs/` altına
  bir dosya ekler ve ordered plan'ın `G11` satırını bu dosyaya bağlar.
