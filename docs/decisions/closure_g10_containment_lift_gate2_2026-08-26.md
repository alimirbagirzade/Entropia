# ADR-0002 §16 **Gate 2**: `C9` / ADIM 20 uygulamasına başlama onayı (kapı **G10**)

> **BU BELGEDE HİÇBİR ÜRÜN SEMANTİĞİ KARARA BAĞLANMAMIŞTIR.** Yazarın rolü **hazırlık**tır.
> §Karar'ın imza bloğunu yalnız ürün sahibi / maintainer doldurur.
> `closure_g8_dst_fold_gap_2026-08-25.md` ve `closure_g14_net_conflict_policy_2026-08-25.md`
> ile aynı disiplin.

- **Tarih:** 2026-08-26
- **Base:** `origin/main` @ `6759a495` (`docs(stage-117): G11 + G12 imzalandı — C6'yı tutan son iki kapı açıldı (#849)`)
  — ilk ölçüm `bda4aba8`'de yapıldı; **#848, #847 ve #849 bu belge yazılırken indi** ve ölçüm
  her seferinde taze tabana karşı **yeniden** koşuldu (§Ölçüm 3). Bu belgenin kendisi
  STALE-BY-DEFAULT kuralına üç kez tabi oldu ve üçünde de düzeltildi.
- **İzleme:** GitHub issue **YOK** — bu kapı bir issue'da değil, ADR-0002 §16'nın gövdesinde yaşıyor.
- **Bloklar:** `C9` (containment lift) — planın kendi mutlak kapı listesinde md. 4.
- **Neden şimdi:** kapı **dokuz slice boyunca hiç talep edilmedi** (ADIM 77, 85, 86, 92 ve
  `STAGE2_HANDOFF.md` beş ayrı yerde *"hiç talep edilmedi"* diye kaydeder). Bu belge ondan
  önce **imzalanacak bir yer olmadığını** ölçer ve o yeri açar.

Satır numarası bilerek yazılmamıştır (CLAUDE.md §Conventions: sembol adı yaz).

---

## Ölçüm 1 — Gate 2 nedir, ve §16 onu neden ADIM 20 için ayırıyor

ADR-0002 §16 (*Stopping condition — discharged, 2026-08-05*) kapıyı kendi sözleriyle kurar:

> *"The approval gate was not honoured in order, and that is recorded rather than tidied
> away. The condition read: implementation does not begin until the PO / maintainer approves
> it. ADIM 15, 17, 19 and the ADIM 20 oracle suite all landed while the status was still
> `Proposed` (PRs #566, #573, #575, #581, #583). Approval arrived at ADIM 18. … so the gate
> is not a formality and should hold for **ADIM 20, which is the first slice that changes a
> shipped number**."*

Yani Gate 2 bir **başlama** onayıdır, bitirme onayı değil. §16'nın kaydettiği kusur da tam
olarak budur: onay, iş **indikten sonra** geldi. Kapının bugün anlamlı olmasının tek yolu,
tersinin yapılmasıdır.

**Gate 1 emsali sevk edilmiş:** ADR §13.2 (*"Signed by the PO (`alimirbagirzade`),
2026-08-17. This is §16's **Gate 1**, requested and granted in session."*) — `G9` + `G13`.
Gate 2 aynı biçimde yazılır.

## Ölçüm 2 — Kapının şekli, `G8`/`G11`/`G12`/`G14`'ten **farklı**

Diğer kapılar bir **ürün semantiği** sorar (NET ne demek, fold bloklamalı mı, ertelenmiş
fill nasıl admit edilir). Gate 2 hiçbir semantik sormaz; **sıra** sorar. Bu yüzden:

- cevabı bir seçenek tablosu değil, bir **an**dır;
- ertelenmesi hiçbir şeyi bloklamaz — `C9` zaten başka on kırmızıyla bloklu;
- ama **verilmemesi de kayıt gerektirir**, yoksa bir sonraki oturum `STAGE2_HANDOFF.md`'nin
  *"hiç talep edilmedi"* satırını okur ve bunu *"sorulmadı"* sanar. **Sorulmuştur.**

## Ölçüm 3 — Talep anındaki ön koşul durumu (2026-08-26, `bda4aba8`)

> **BAŞLIK DEĞİŞTİRİLMEDİ, GÖVDE GÜNCELLENDİ (ADIM 120, 2026-08-27).** Başlık *talep
> anını* adlandırır ve o an tarihseldir; `docs-history-guard` bir `## ` başlığının
> **kökünü** karşılaştırır ve **yeniden adlandırmayı bloklar** (ADIM 61/111). Aşağısı
> artık bir **ölçüm ZİNCİRİDİR** ve son tabanı **`f0be03f1`**'dir.

`P-C2 §C.7`'nin 22 ön koşulu art arda **dört** tabana karşı ölçüldü. Eski ölçümler
**silinmedi, tarihiyle bırakıldı** — her biri o an doğruydu ve **bayatladı**:

- `bda4aba8` (#847 inmeden önce): **12 yeşil / 10 kırmızı**. Bağımsız ikinci türetim — o
  sırada henüz açık olan PR #847'nin `closure_c9_containment_lift_verdict_2026-08-26.md`
  belgesi de **12** diyordu.
- `ae18f46b` (#847 indikten + `#559` kapatıldıktan sonra): **13 yeşil / 9 kırmızı** — ön koşul **21** döndü.
- `6759a495` (#849 indikten sonra): **16 yeşil / 6 kırmızı** — ön koşul **13**, **14** ve **2** döndü.
- **`f0be03f1` (#850 + #851 + #853 indikten sonra, 2026-08-27): 18 yeşil / 4 kırmızı** —
  ön koşul **15** ve **16** döndü (ADIM 119). **Kalan dört kırmızı: 17 · 18 · 20 · 22.**

Kırmızıların **sınıflandırması düzeltildi** ve bu, kapının cevabını doğrudan etkiler
(satırlar `f0be03f1`'e karşı **yeniden** ölçüldü, sayı taşınmadı):

| ön koşul | sınıf | durum |
|---|---|---|
| 13 (`G11`) · 14 (`G12`) | ~~ÜRÜN KARARI~~ **YEŞİL** | ikisi de **imzalandı** (ürün sahibi, 2026-08-26; #849 → `6759a495`) |
| 2 (`_phase_tail` ayrılamaz) | ~~ÜRÜN KARARI~~ **DÜŞTÜ** | `G12` = **`A` (admission'da blokla)** + alt-karar *"ikisi de"* (Ready Check blocker **ve** admission reddi). Scaling paylaşımlı koşuda hiç admit edilmiyorsa `_phase_tail`'in **ayrılması gerekmiyor** — ön koşul karşılanmadı, **konusuz kaldı** |
| 20 (`G14`) | **KARAR + MÜHENDİSLİK** | Karar 1 imzalı (`C` şimdi + `B` `C9` öncesi) — imzayı **#847** (`ae18f46b`) getirdi, ~~o sırada açıktı~~ **merge edildi**; `C` yarısı **#850** (`42352048`, ADIM 118) ile **sevk edildi**. `B` yarısı (NET enum'unun kaldırılması) bir **migration** ve **yazılmadı**; **Karar 3 de İMZALI** (aynı #850; `☑ Onaylanan metin: rules.py::_net_policy_warning`) — **açık olan YALNIZ Karar 2'dir** (`'NET'` taşıyan mevcut satırların dispozisyonu) ve `#544` **OPEN**. **Bu satır, yeniden talep koşulunun md. 2'si — ve tek gerçek blocker odur.** |
| 21 (`G8`) | **ESASEN YEŞİL, defter işi kaldı** | `A1+B2+C1` imzalı **ve sevk edilmiş** (#847 → `ae18f46b`; `shared/dst.py::is_nonexistent_local_time`, iki okuyucu da çağırıyor). Ön koşulun **lafzı** *"GH #559 kapalı"* diyor; **2026-08-27'de yeniden ölçüldü: issue `CLOSED/COMPLETED` (2026-08-26T11:29:21Z)** → lafız da sağlandı. **AMA G8 md. 4 sağlanMADI:** issue'nun **tek** yorumu 2026-08-25 tarihli ve o, kapatmadan ÖNCE kuralın yazılmasını isteyen yorumdur — kapanış yorumu **seçilen şıkkı (`A1+B2+C1`) ve dosyayı adlandırmıyor** (#558 emsali). Ön koşul yine de yeşildir (ADIM 90: üç düzlem ayrışınca **otorite imza kutusudur**, ve o kutu dolu + kod sevk edildi); eksik olan **defter işidir ve insan eylemidir** |
| 15 (OD-6) · 16 (OD-1) | ~~MÜHENDİSLİK~~ **YEŞİL** | ADIM 119 (#851 → `82c98660`) ikisini de sevk etti **ve wired**: `allocation/shared_mode_admission.py::non_executing_sleeve_holders` / `::mixed_record_time_bases`, `commands/backtest_run.py` admission'ında `_readiness_blocked` ile O-02 zarfı (`ALLOCATION_SHARED_MODE_NON_EXECUTING_ITEM` / `ALLOCATION_SHARED_MODE_MIXED_RECORD_TIME_BASIS`). **Tanımlı olmak yetmez, ulaşılabilir olduğu ayrıca ölçüldü.** |
| 17 (OD-2) · 18 (OD-3) | **MÜHENDİSLİK** | kararları **2026-08-05'te ADR §13.1 ile imzalı**; mark policy yazılmadı ve iki etiket flip'ini §13.1 zaten **ADIM 20'ye verdi** — `f0be03f1`'de yeniden okundu: `MARK_STALENESS_POLICY = "undefined_pending_od2"`, `CONTENTION_SELECTION_STATUS = "recommended_pending_approval"` |
| 22 (A15/A16) | **`C9`'UN KENDİ TESLİMATI** | — |

**Bu tablo bir düzeltmedir.** #847 ile main'e inen `docs/audit/closure_c9_containment_lift_verdict_2026-08-26.md`'nin *"kırmızıların 10'unun 10'u da ya bir insan
imzasıdır ya da imzasız bir ürün kararı"* diyor; **15/16/17/18 için yanlış** — o dördü imzalı
bir kararın altındaki mühendislik işidir (ADR §13.1, yedi OD'nin yedisi de `(a)`'ya çözüldü).

## Ölçüm 4 — ASIL NOKTA: Gate 2'yi vermek `C9`'u başlatmaz

Onay verilse bile bugün yazılabilecek `C9` kodu **yoktur**: `G14`'ün `B` yarısı bir migration
olarak duruyor (`allocation/enums.py::CrossItemConflictPolicy.NET` **hâlâ ağaçta**).
`G8` (#847), sonra `G11`+`G12` (#849) bu belge yazılırken indi ve **dört kırmızıyı** düşürdü
— **altı tane kaldı**, ve altısının **beşi** artık mühendislik. Yani Gate 2 bugün ne bir kapıyı açar ne de bir işi serbest bırakır —
**yalnız sırayı belirler.**

Bu, seçenekleri ucuzlatır: ikisi de bugün hiçbir şeyi kırmaz, ayrıştıkları eksen
*"onay ne zaman anlamlıdır"*dır.

---

## Karar — Gate 2 ne zaman verilir

| # | Seçenek | Ölçülmüş sonucu | Bedeli |
|---|---|---|---|
| **A** | **ŞİMDİ ver** — ADR §13.2 tarzı imzalı amendment | §16'nın kapısı **ilk kez sırayla** tutulmuş olur: onay, tek satır `C9` kodu yazılmadan önce | onay, uygulanamayan bir işe verilir; bir sonraki okuyucu *"onaylı"* görüp kalan on kırmızıyı hafife alabilir |
| **B** | **ERTELE** — kalan karar kapıları kapanınca iste | onay, uygulanabilir bir işe verilir; §16'nın *"formalite değil"* cümlesi korunur | kapı açık kalır ve talep edildiği **kaydedilmezse** yine *"hiç sorulmadı"* diye okunur — bu belge o riski kapatır |
| **C** | **REDDET** — `C9` programı durdurulsun | `C9` kapanır, containment kalıcı olur | ADR-0002'nin tamamı ve `C1`–`C4` yatırımı sevk edilmemiş kalır; bu ayrı ve çok daha büyük bir karardır |

☑ **Seçim:** **B — ERTELE** (talep edildi, bilerek verilmedi)
☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-26

> **Ürün sahibinin gerekçesi (oturum içinde seçilen şıkkın metni, verbatim):** *"Şimdi verme
> — 9 kırmızı dururken sırası değil. Onay, uygulanacak bir şey olduğunda anlamlı. … Gate 2'yi
> şimdi vermek onu tekrar bir formaliteye çevirir — §16'nın kaydettiği kusurun aynası."*

**Bu bir RED DEĞİLDİR.** Kapı açıktır; ertelenmiştir. Yeniden talep edilmesi için gereken
koşul aşağıda.

---

## Yeniden talep koşulu (uygulayıcı için)

Gate 2 şu üçü birden sağlandığında **yeniden istenir**:

1. ~~`G11` ve `G12` imzalı~~ **SAĞLANDI** (#849 → `6759a495`; `G12` = `A`, ön koşul 2'yi de
   konusuz bıraktı);
2. ~~`G14`'ün `B` yarısı (`NET` enum'unun kaldırılması + Karar 2'nin migration şıkkı) **sevk
   edilmiş**, `#544` kapalı (ön koşul 20)~~ **SAĞLANDI — 2026-08-27; 2026-08-28'de bu belge
   için YENİDEN ÖLÇÜLDÜ, taşınmadı.** `B` sevk edildi:
   `backend/alembic/versions/0044_drop_net_conflict_policy.py` (ADIM 124, #859) — `NET`
   enum'dan düştü, kolona CHECK kısıtı eklendi, `B3`'ün halt guard'ı ile; bugün
   `domain/allocation/enums.py` `NET`'i yalnız *kaldırıldı* diye **anıyor**, üye olarak
   taşımıyor. `#544` **CLOSED / COMPLETED** (`2026-08-27T13:05:47Z`). `G14`'ün **dört**
   kararının dördü de imzalı — **bölüm bazında** okundu, dosya düzeyinde grep'le değil
   (ADIM 119'un tuzağı): Karar 1 `C`+`B` (2026-08-26), Karar 2 `B3` (2026-08-27),
   Karar 3 metin (2026-08-26), Karar 4 `B0` (2026-08-27).
3. ~~`G8` merge edilmiş~~ **SAĞLANDI** (`ae18f46b`); ~~geriye yalnız `#559`'un kapatılması kaldı~~
   **`#559` de KAPANDI** (`CLOSED/COMPLETED`, 2026-08-26T11:29:21Z) → **md. 3 tamamen sağlandı.**
   Açık kalan **tek** artık defter işidir: G8 md. 4 kapanış yorumunun seçilen şıkkı ve dosyayı
   adlandırmasını ister (#558 emsali) ve o yorum **yazılmadı**. **İnsan eylemi; ajan bu issue'ya
   dokunmaz.** Bu artık ön koşul 21'i kırmızıya çevirmez — yeniden talep koşulunu da bloklamaz.

~~O noktada kalan kırmızılar 15/16/17/18/22 olur; beşi de **mühendislik**~~ — **o nokta
2026-08-27'de GELDİ, ve tahmin iki yönden de yanlış çıktı.** Kalan kırmızılar **17/18/22**:
15 ve 16 ADIM 119'da sevk edildi (`domain/allocation/shared_mode_admission.py`). Ve kalan
üçü de artık *"`C9`'un hemen öncesindeki iş"* değil, **`C9`'un KENDİSİ**: 17 ve 18 için ürün
sahibi 2026-08-28'de `C` dedi (*"şimdi çözme, `C9`'a adıyla devret"* — ADIM 129), 22'nin
kalanı ise `C9`'un kendi A15 bump'ı ile A22 suite kapısıdır. Yani Gate 2 **artık
uygulanabilir bir işe verilir** ve §16'nın kapısı ilk kez amacına hizmet eder.

---

## Yeniden talep — Gate 2, **İKİNCİ** istek (2026-08-28, ADIM 130)

> **ADIM 130'da bu bölüm bir ÖLÇÜMDÜ ve kutusu BOŞTU.** Ölçüm şuydu: §Yeniden talep
> koşulunun **üç maddesi de** tahliye edildi, yani `B — ERTELE`'nin dayandığı gerekçe artık
> ayakta değil. **ADIM 131'de (2026-08-28) kutu İMZALANDI: `A` — Gate 2 ONAYLANDI.**
> Aşağısı artık bir ölçüm **ve** bir karardır; ölçüm satırları el değmemiştir.

### Üç maddenin ölçümü (`80f6cc7d`, 2026-08-28)

| # | Koşul | Durum | Ölçüm |
|---|---|---|---|
| 1 | `G11` + `G12` imzalı | ✅ | #849 (`6759a495`); kodu ADIM 125 ile indi (`execution/shared_shapes.py`) |
| 2 | `G14`'ün `B` yarısı sevk edilmiş + `#544` kapalı | ✅ **YENİ** | `0044_drop_net_conflict_policy` + `enums.py`'de `NET` üye değil; `#544` `CLOSED/COMPLETED` `2026-08-27T13:05:47Z` |
| 3 | `G8` merge + `#559` kapalı | ✅ | `ae18f46b`; `#559` `CLOSED/COMPLETED` `2026-08-26T11:29:21Z` |

**md. 2, ilk talebin tek eksiğiydi ve iki gün sonra kapandı.** Bu belgenin §Bu belgenin
kapsamadıkları bölümündeki *"Yeniden talep koşulunun md. 2'si sağlanmamıştır"* cümlesi o
yüzden **bayattır** ve orada işaretlenmiştir — silinmemiştir.

### Ürün sahibinin ilk gerekçesi, bugünkü dünyaya karşı

`B` şıkkının gerekçesi verbatim şuydu: *"Şimdi verme — **9 kırmızı** dururken sırası değil.
Onay, uygulanacak bir şey olduğunda anlamlı."* Bugün kırmızı sayısı **3**'tür (17/18/22) ve
**üçü de `C9`'un kendi teslimatıdır** — yani onayın önünde artık `C9`-dışı hiçbir iş yok.
Gerekçenin kendi koşulu karşılandı.

### Karar kutusu — **İMZALI: `A` (2026-08-28)**

☑ **A — ŞİMDİ ver** (Gate 2 onaylandı; `C9` / ADIM 20 PR'ı açılabilir)
☐ **B — YİNE ERTELE** (gerekçe aşağıya yazılır; kapı açık kalır)
☐ **C — REDDET** (`C9` programı durdurulur; containment kalıcı olur)

☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-08-28

> **Gerekçe.** Karar oturum içinde, ADIM 130'un ölçümü sunulduktan sonra verildi
> (2026-08-28). **Seçilen şıkkın kendisine sunulan metni verbatim:** *"Gate 2 onaylanır;
> `C9` / ADIM 20 PR'ı açılabilir hale gelir. Kapı
> (`test_lifting_containment_requires_gate2_approval`) kendiliğinden susar — testte
> değiştirilecek literal yok. Kalan kırmızılar 17/18/22 ve üçü de `C9`'un kendi teslimatı;
> `C9` YALNIZ koşar, başka PR açık olamaz. A-08 (#514) yine de RC verdict'ini ayrıca
> bloklar."*
>
> **Serbest metinli bir gerekçe ALINMADI ve UYDURULMADI** — imzacı üç şıktan birini seçti;
> yukarıdaki alıntı **şıkkın metnidir**, imzacının cümlesi değildir. ADIM 129'un `C`
> kararında da aynı biçim kullanıldı.
>
> **Bu onay `C9`'u BAŞLATIR, BİTİRMEZ.** §Karar tablosunun `A` satırının kendi bedeli
> yerinde duruyor: *"bir sonraki okuyucu 'onaylı' görüp kalan kırmızıları hafife
> alabilir."* Kalan üç kırmızı **17 / 18 / 22**'dir ve üçü de `C9`'un teslimatıdır.

### Bu talebin ZORLANIYOR olması (ADIM 130'un mühendislik yarısı)

İlk talep, `B` şıkkının kendi bedelini şöyle yazmıştı: *"kapı açık kalır ve talep edildiği
**kaydedilmezse** yine 'hiç sorulmadı' diye okunur."* Bir belgeye kaydetmek bunu yalnızca
**hatırlatır**. Ölçüldü (2026-08-28): `backend/` ağacının **tamamında** `G10` ya da
"Gate 2" geçen **sıfır** satır vardı — yani sıralı planın `C9` stop condition'ı
(*"Any of the 22 preconditions unmet, or **G10 unsigned** → do not open this PR"*) hiçbir
kapı tarafından zorlanmıyordu: `C9` bayrağı çevirebilir ve **her test yeşil kalırdı**.

Artık zorlanıyor:
`tests/unit/oracles/test_oracle_portfolio_containment_gate.py::test_lifting_containment_requires_gate2_approval`
bu **dosyayı okur** ve `SHARED_ALLOCATION_STATUS == "active_v1"` iken Gate 2 onaylı değilse
kırmızı verir. Kapı **fail-closed**'dur: kutu okunamazsa (bölüm silinmiş, iki şık birden
işaretlenmiş, dosya taşınmış) test *sessizce geçmez*, **patlar** — K-07 idiomu.

**Onay verildiğinde yapılacak tek şey yukarıdaki kutuda `A`'yı işaretlemektir**; kapı bunu
kendiliğinden okur ve susar. Testte değiştirilecek bir literal yoktur.

## Bu belgenin kapsamadıkları (dürüst sınır)

- **`G16` / A-08 (#514) ayrı ve bağımsızdır.** Gate 2 verilse de nihai RC verdict'i o insan
  denetimi açıkken sonuçlanamaz; ajan o issue'yu ne açar ne kapar (`human-only`).
- **Hiçbir ön koşulu kapatmaz.** Ön koşul ölçümü bu belgeden bağımsızdır; **son taban
  `f0be03f1` ve sayı 18/22'dir** (§Ölçüm 3'ün zinciri). Buradaki sayı **türetilmiş bir
  rapordur, otorite değildir** — kararı okuyan her oturum onu koda karşı yeniden ölçmelidir.
- ~~**Ön koşul 20 hâlâ kırmızıdır ve öyle sayılmıştır.** `G14` Karar 1 imzalı (`C` şimdi +
  `B` `C9` öncesi) ama `B` sevk edilmedi, Karar 2 (mevcut `'NET'` satırları) ve Karar 3
  (`C`'nin metni) **boş**, `#544` açık. İmzalı bir Karar 1, kapatılmış bir kapı değildir.~~
  **BAYAT (2026-08-28'de ölçüldü, ADIM 130).** `B` sevk edildi (`0044_drop_net_conflict_policy`,
  ADIM 124), dört kararın dördü de imzalı, `#544` `CLOSED/COMPLETED`. **Cümlenin KURALI
  yine de doğruydu ve korunuyor** — imzalı bir Karar, kapatılmış bir kapı değildir; bu
  belgedeki `B — ERTELE` imzası da tam olarak odur.
- ~~**Ertelemenin gerekçesi ZAYIFLADI ama DÜŞMEDİ.** #847 + #849 dört kırmızı düşürdü ve
  `G11`/`G12` artık imzalı. §Karar'ın `B` şıkkı *"kalan **karar** kapıları kapanınca"* der —
  **`G14` hâlâ açıktır**: Karar 1 imzalı (`C` şimdi + `B` `C9` öncesi) ama `B` sevk edilmedi,
  Karar 2 ve 3 **boş**, `#544` açık. Yeniden talep koşulunun md. 2'si sağlanmamıştır.~~
  **BAYAT (2026-08-28).** `G14`'ün dört kararı da imzalı ve `B` sevk edildi → §Karar'ın `B`
  şıkkının *"kalan **karar** kapıları kapanınca"* koşulu **karşılandı**; yeniden talep
  koşulunun md. 2'si **sağlanmıştır**. Talep §Yeniden talep — Gate 2, **İKİNCİ** istek
  bölümündedir ve kutusu **boştur**.
