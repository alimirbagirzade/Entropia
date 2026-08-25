# `NET` cross-item conflict policy: **tanımla**, **kaldır**, yoksa **yalnız bildirimi düzelt**? (kapı **G14**)

> **BU BELGEDE HİÇBİR KARAR VERİLMEMİŞTİR.** Yazarın rolü **hazırlık**tır. §Karar'ın
> imza bloğu **boştur** ve onu yalnız ürün sahibi / maintainer doldurabilir.
> `closure_g11_deferred_fill_admission_2026-08-18.md` ile aynı disiplin.

- **Tarih:** 2026-08-25
- **Base:** `origin/main` @ `74db6ff5`
- **İzleme:** GH **#544** (`product-decision`, `blocks-adim-19`) — **2026-08-25'te yeniden
  AÇILDI**; 2026-08-18'de #559 ile **bir saniye arayla**, sıfır yorum / sıfır closing PR /
  sıfır kod değişikliğiyle kapatılmıştı (`final_closure_delta_audit_2026-08-25.md` §4 C-5).
- **Kapsam:** `CrossItemConflictPolicy.NET` — anlamı, sevk edilmiş iki davranışı ve
  kullanıcıya ne söylendiği.
- **Bloklar:** `C9` (containment lift) — ön koşul **20**.
- **BLOKLAMAZ:** `C2`, `C3`, `C4`, `C6`, `G11`, `G12`, A-08.
- **Neden şimdi:** #544 yazıldığından beri **dünya değişti** — Ölçüm 2. Kapı, issue kapalıyken
  *"sağlandı"* diye okunuyordu.

Satır numarası bilerek yazılmamıştır (CLAUDE.md §Conventions: sembol adı yaz).

---

## Ölçüm 1 — İki yıl önceki tespit hâlâ **kelimesi kelimesine** geçerli

`e2fa521..74db6ff5` aralığında üç yüzeyin **hiçbiri** değişmedi (diff boş):

| yüzey | sevk edilen metin |
|---|---|
| `domain/allocation/rules.py` (`CONFLICT_POLICY_NET_V1` uyarısı) | *"the engine executes NET conservatively as BLOCK_OPPOSITE"* |
| `frontend/src/lib/allocation.ts` | `NET: "Net (V1: executed as Block opposite)"` |
| `domain/allocation/enums.py` (`CrossItemConflictPolicy` docstring) | aynı iddia |

`SHARED_ALLOCATION_STATUS = "future_dev"` olduğu için **hiçbir shared run admit edilmiyor**,
yani bu üç metin gerçekleşemeyen bir davranışı ilan ediyor. #544'ün *"safe to fix now,
independent of the decision"* dediği metin düzeltmesi **yapılmadı**.

## Ölçüm 2 — YENİ: artık **TEK değere karşılık İKİ sevk edilmiş davranış** var

#544 yazıldığında NET'in tek bir davranışı vardı (sıralı motorda downgrade). Bugün iki tane:

| yol | ne yapar | sembol |
|---|---|---|
| **sıralı motor** (bugün üretimde koşan) | NET'i **BLOCK_OPPOSITE'a downgrade eder** ve L4'te açıklar | `engine.py::conflict_downgraded_from_net` |
| **faz döngüsü** (`C4` ile bağlandı, contained) | NET'i **REDDEDER** — `UnsupportedConflictPolicyError` | `execution/arbitration.py::NET_SUPPORT_STATUS = "undefined_in_canon"` |

Faz döngüsünün gerekçesi kendi docstring'inde yazılı ve **doğrudur**:

> *"presenting a block as if it were netting would advertise a semantics canon has never
> defined … Refusing produces no Result at all, which is strictly safer than producing one
> whose policy label does not describe what ran."*

**Sonuç: bildirim artık DAHA yanlış, daha az değil.** Üretim *"conservatively as
BLOCK_OPPOSITE"* diye ilan ediyor; onu koşacak olan kod **reddediyor**. Üstelik beş açık
semantiğin kaynağı olan `NET_TRACKING_ISSUE` sabiti (2026-08-18 → 2026-08-25 arası) **kapalı**
bir issue'yu gösteriyordu.

## Ölçüm 3 — Beş tanımsız semantik **zaten kaynakta sayılı**

`execution/arbitration.py::NET_UNDEFINED_SEMANTICS`, tanımlama seçeneğinin cevaplaması
gereken listeyi birebir taşıyor — bu belge onu **yeniden yazmıyor**, adlandırıyor:

1. **netting price** — iki karşıt item pozisyonu hangi fiyattan offset olur
2. **position custody** — netlenen pozisyonu hangi item'ın defteri tutar, diğerinde ne kalır
3. **fee attribution** — offset bir komisyon mu, iki mi, sıfır mı öder
4. **realized PnL attribution** — netlenen sonuç iki item'a nasıl bölünür
5. **margin / collateral** — netlenmiş çift ne kadar sermaye bağlar (Master Ref §10.2 bunu
   **var olmayan** bir portföy risk modeline devrediyor)

Beşi de ürün kararıdır; biri tahmin edilirse kullanıcının kanona karşı denetleyemeyeceği
sayılar üretilir.

## Ölçüm 4 — KRİTİK: **kaldırmak metin değişikliği DEĞİL, migration**

`conflict_policy` kalıcı bir kolondur:

- tablo **`portfolio_allocation_plan`**, `0035_portfolio_rules` ile eklendi;
- tip `enum_column(CrossItemConflictPolicy, "allocation_conflict_policy")` →
  **VARCHAR + CHECK constraint** (`native_enum=False`, `validate_strings=True`);
- ORM tarafı `infrastructure/postgres/models/allocation.py`, nullable.

Yani enum'dan `NET`'i düşürmek **CHECK'i yeniden yazan bir alembic revision'ı gerektirir**,
ve **`'NET'` taşıyan mevcut satırlar yeni CHECK'i ihlal eder**. Migration onların ne olacağına
karar vermek zorundadır — ve bu seçeneğin asıl bedeli budur, kod satırı sayısı değil:

- `BLOCK_OPPOSITE`'a yeniden yazmak → **kullanıcının kaydettiği yapılandırmayı sessizce
  değiştirmek**; bu deponun *"silent fallback"* yasağının tam da kendisi;
- satırları olduğu gibi bırakıp okumayı gevşetmek → enum kaldırılmış **olmaz**;
- migration'ı `'NET'` satırı varsa **durdurmak** → dürüst, ama operatöre elle iş bırakır.

Ek yüzeyler: `frontend/src/lib/allocation.ts::CONFLICT_POLICIES` + label, `Portfolio.tsx`'in
açıklama metni, ve davranışı pinleyen **beş test dosyası** (`test_allocation_rules.py`,
`test_allocation_persistence.py`, `test_backtest_output.py`,
`test_backtest_cross_item_arbitration.py`, `test_oracle_portfolio_capital.py`).

---

## Karar 1 — NET'in geleceği

| # | Seçenek | Ölçülmüş sonucu | Bedeli |
|---|---|---|---|
| **A** | **TANIMLA** — Ölçüm 3'ün beş sorusunu cevapla | `arbitration.py` refüzü gerçek bir kurala dönüşür; `C9` sonrası NET **çalışır** | beş ürün kararı + netleme aritmetiği + golden fixture'lar; **açık ara en pahalı**, ve Master Ref §10.2 madde 5 için bir risk modeli **istiyor** |
| **B** | **KALDIR** — enum değerini düşür | değer artık kaydedilemez; iki yollu çelişki kökten biter | **migration + mevcut satır kararı** (Ölçüm 4) + frontend + beş test dosyası; **geri alması zor** |
| **C** | **DEĞERİ TUT, yalnız BİLDİRİMİ düzelt** — üç metin bugünkü gerçeği anlatsın | #544'ün kendi *"safe to fix now"* önerisi; kod davranışı değişmez; migration yok | **`G14`'ü KAPATMAZ** — bkz. aşağıdaki uyarı |

> **UYARI — C tek başına kapıyı kapatmaz, ve bu ölçüldü.** Ön koşul 20 NET'in *anlamının*
> kararını ister, bildiriminin doğruluğunu değil. `C` doğru ve ucuz bir düzeltmedir
> (bugün kullanıcıya yalan söylenmesini durdurur), ama `C9` öncesinde **A ya da B yine de
> gereklidir**. `C`'yi *"halloldu"* diye işaretlemek, bu belgenin var olma sebebi olan
> hatanın aynısı olur.
>
> **Kombinasyon serbesttir ve muhtemelen doğrusudur:** `C` **şimdi**, `A`/`B` `C9` öncesi.

☐ **Seçim:** ____   ☐ **İmza:** ____________   ☐ **Tarih:** __________

## Karar 2 — YALNIZ `B` seçilirse: `'NET'` taşıyan mevcut satırlar

| # | Seçenek | Ölçülmüş sonucu |
|---|---|---|
| **B1** | `BLOCK_OPPOSITE`'a yeniden yaz | veri kaybı yok, ama **kullanıcı yapılandırması sessizce değişir** (silent-fallback yasağı) |
| **B2** | `NULL`'a çevir | kolon zaten nullable; *"seçim yapılmamış"* demek, yanlış bir seçim atfetmekten dürüsttür |
| **B3** | Satır varsa migration **DURSUN** | en dürüstü; operatöre elle karar bırakır, otomatik deploy'u bloklar |

☐ **Seçim:** ____   ☐ **İmza:** ____________   ☐ **Tarih:** __________

## Karar 3 — `C` seçilirse: bildirim ne DESİN

Metin, sevk edilmiş **iki** davranışı da doğru anlatmalıdır (Ölçüm 2), yoksa aynı kusurun
yeni sürümü yazılmış olur. Ölçülmüş doğru içerik:

- containment yürürlükteyken **hiçbir shared run admit edilmiyor** — downgrade *gerçekleşmiyor*;
- sıralı motorda değer **BLOCK_OPPOSITE olarak** koşar;
- faz döngüsü onu **reddeder**;
- NET'in kanonik tanımı **yok** ve beş semantiği `NET_UNDEFINED_SEMANTICS`'te sayılı.

☐ **Onaylanan metin:** ____________   ☐ **İmza:** ____________   ☐ **Tarih:** __________

---

## İmzadan SONRA yapılacaklar (uygulayıcı için)

1. Kararı bu belgeye yaz.
2. `C`: üç yüzey (`rules.py` uyarısı, `enums.py` docstring'i, `lib/allocation.ts` label'ı)
   **birlikte** güncellenir — biri unutulursa çelişki devam eder. `Portfolio.tsx`'in
   açıklama cümlesi de aynı partide.
3. `B`: alembic revision + Karar 2'nin şıkkı + frontend + beş test dosyası; migration
   **up/down/up** ile doğrulanır (CLAUDE.md §Local verify).
4. `A`: beş semantik ADR-0002'ye amendment olarak girer; `NET_SUPPORT_STATUS` ve
   `NET_UNDEFINED_SEMANTICS` kararın adına çevrilir; golden digest'ler **bump** ister.
5. Her hâlde `arbitration.py::NET_TRACKING_ISSUE` bu dosyayı ya da kararın adını
   göstermelidir — **kapalı bir issue'yu göstermemelidir** (2026-08-18'de öyle olmuştu).
6. #544 **ancak bu belge imzalandıktan sonra** kapatılır; kapanış yorumu seçilen şıkkı ve bu
   dosyayı adlandırır (#558 / Karar 2 emsali).
7. `closure_w0_containment_lift_preconditions_2026-08-17.md` §2 ön koşul **20** ve
   `final_closure_delta_audit_2026-08-25.md` §8 satır 20 güncellenir.
