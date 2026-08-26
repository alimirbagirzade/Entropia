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

`P-C2 §C.7`'nin 22 ön koşulu **iki kez** ölçüldü:

- `bda4aba8` (#847 inmeden önce): **12 yeşil / 10 kırmızı**. Bağımsız ikinci türetim — o
  sırada henüz açık olan PR #847'nin `closure_c9_containment_lift_verdict_2026-08-26.md`
  belgesi de **12** diyordu.
- `ae18f46b` (#847 indikten + `#559` kapatıldıktan sonra): **13 yeşil / 9 kırmızı** — ön koşul **21** döndü.
- `6759a495` (#849 indikten sonra): **16 yeşil / 6 kırmızı** — ön koşul **13**, **14** ve **2** döndü.

Kırmızı 10'un **sınıflandırması düzeltildi** ve bu, kapının cevabını doğrudan etkiler:

| ön koşul | sınıf | durum |
|---|---|---|
| 13 (`G11`) · 14 (`G12`) | ~~ÜRÜN KARARI~~ **YEŞİL** | ikisi de **imzalandı** (ürün sahibi, 2026-08-26; #849 → `6759a495`) |
| 2 (`_phase_tail` ayrılamaz) | ~~ÜRÜN KARARI~~ **DÜŞTÜ** | `G12` = **`A` (admission'da blokla)** + alt-karar *"ikisi de"* (Ready Check blocker **ve** admission reddi). Scaling paylaşımlı koşuda hiç admit edilmiyorsa `_phase_tail`'in **ayrılması gerekmiyor** — ön koşul karşılanmadı, **konusuz kaldı** |
| 20 (`G14`) | **KARAR + MÜHENDİSLİK** | Karar 1 açık PR #847'de imzalı (`C` şimdi + `B` `C9` öncesi); `B` bir **migration**, yazılmadı; Karar 2/3 boş |
| 21 (`G8`) | **ESASEN YEŞİL, defter işi kaldı** | `A1+B2+C1` imzalı **ve sevk edilmiş** (#847 → `ae18f46b`; `shared/dst.py::is_nonexistent_local_time`, iki okuyucu da çağırıyor). Ön koşulun **lafzı** *"GH #559 kapalı"* diyor ve issue hâlâ `OPEN/REOPENED` — ama ADIM 90 kuralı gereği üç düzlem ayrıştığında **otorite imza kutusudur**, ve o kutu dolu. Kalan tek iş issue'nun kapatılması: **insan eylemi**, G8 belgesinin kendi md. 4'ü |
| 15 (OD-6) · 16 (OD-1) · 17 (OD-2) · 18 (OD-3) | **MÜHENDİSLİK** | kararları **2026-08-05'te ADR §13.1 ile imzalı**; blocker'lar/mark policy yazılmadı, 17-18 zaten §13.1 tarafından ADIM 20'ye verilmiş |
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
2. `G14`'ün `B` yarısı (`NET` enum'unun kaldırılması + Karar 2'nin migration şıkkı) **sevk
   edilmiş**, `#544` kapalı (ön koşul 20);
3. ~~`G8` merge edilmiş~~ **SAĞLANDI** (`ae18f46b`); geriye yalnız `#559`'un kapatılması
   kaldı — G8 belgesinin md. 4'ü kapanış yorumunun seçilen şıkkı ve dosyayı adlandırmasını
   ister (#558 emsali). **İnsan eylemi; ajan bu issue'yu kapatmaz.**

O noktada kalan kırmızılar 15/16/17/18/22 olur; beşi de **mühendislik** ve beşi de
`C9`'un ya doğrudan teslimatı ya da onun hemen öncesindeki iştir. Gate 2 orada
uygulanabilir bir işe verilir ve §16'nın kapısı ilk kez amacına hizmet eder.

## Bu belgenin kapsamadıkları (dürüst sınır)

- **`G16` / A-08 (#514) ayrı ve bağımsızdır.** Gate 2 verilse de nihai RC verdict'i o insan
  denetimi açıkken sonuçlanamaz; ajan o issue'yu ne açar ne kapar (`human-only`).
- **Hiçbir ön koşulu kapatmaz.** 16/22 ölçümü bu belgeden bağımsızdır ve tabanı `6759a495`'tir.
- **Ön koşul 20 hâlâ kırmızıdır ve öyle sayılmıştır.** `G14` Karar 1 imzalı (`C` şimdi +
  `B` `C9` öncesi) ama `B` sevk edilmedi, Karar 2 (mevcut `'NET'` satırları) ve Karar 3
  (`C`'nin metni) **boş**, `#544` açık. İmzalı bir Karar 1, kapatılmış bir kapı değildir.
- **Ertelemenin gerekçesi ZAYIFLADI ama DÜŞMEDİ.** #847 + #849 dört kırmızı düşürdü ve
  `G11`/`G12` artık imzalı. §Karar'ın `B` şıkkı *"kalan **karar** kapıları kapanınca"* der —
  **`G14` hâlâ açıktır**: Karar 1 imzalı (`C` şimdi + `B` `C9` öncesi) ama `B` sevk edilmedi,
  Karar 2 ve 3 **boş**, `#544` açık. Yeniden talep koşulunun md. 2'si sağlanmamıştır.
