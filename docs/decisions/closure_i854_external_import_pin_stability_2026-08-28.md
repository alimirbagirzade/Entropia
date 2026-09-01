<!-- doc-status: current -->
# Dış import pin'i **taşınıyor**: hangi revision çözülsün, ve hangi bedelle (GH #854)

> **BU BELGEDE HİÇBİR ÜRÜN SEMANTİĞİ KARARA BAĞLANMAMIŞTIR.** Yazarın rolü **ölçüm ve
> hazırlık**tır. §Karar'ın imza bloklarını yalnız ürün sahibi / maintainer doldurur.
> `closure_od2_mark_production_binding_2026-08-28.md`, `closure_g15_external_row_winner_2026-08-17.md`
> ve `closure_g14_net_conflict_policy_2026-08-25.md` ile aynı disiplin.

- **Tarih:** 2026-08-28
- **Base:** `origin/main` @ `8b3a24b0` (`docs(stage-133): OD-2 mark yolunun üretime bağlanması (#870)`).
  Ölçüm sırasında açık PR **yoktu** — anlık görüntüdür, garanti değil (ADIM 100).
- **İzleme:** GitHub issue **#854** (açık). İssue'yu kapatmak **insan kararıdır**; bu belge
  ona dokunmaz.
- **Bloklar:** RC verdict'ini **bloklamaz**; tek blocker **A-08 (#514)** ve bu karar o hatta
  dokunmaz. Kusurun kendisi **sevk edilmiş kullanıcı yolundadır**.
- **Neden şimdi:** kusur `G15` §Ölçüm 4'te ölçülüp *"ayrı kalem"* olarak kaydedilmişti ve
  ürün sahibi 2026-08-26'da *"issue açılsın"* imzasını verdi. Bu slice kusurun **testini**
  sevk eder; **düzeltmesini sevk etmez**, çünkü düzeltme bir ürün kararıdır.

Satır numarası bilerek yazılmamıştır (CLAUDE.md §Conventions: sembol adı yaz).

---

## Ölçüm 1 — Mekanizma: **dört** çağrı yeri, **iki** koşulsuz atama

| Yazıcı | Modül | Biçim | Çağrı yeri |
|---|---|---|---|
| `link_batch_to_revision` | `repositories/trade_log.py` | koşulsuz atama | `commands/trade_log.py` — create **ve** revision |
| `link_normalized_to_revision` | `repositories/trading_signal.py` | koşulsuz atama | `commands/trading_signal.py` — create **ve** revision |

İkisi de tek satırlık bir atamadır. **Bu tek bir kusur sınıfıdır, iki ayrı bug değil** — bir
düzeltme bir yüzeyi onarıp diğerini sessizce bırakabilir, o yüzden test iki yüzeyi de sürer.

`commands/trade_log.py::_require_ready_import` **yalnız** status / `accepted_count` / timezone
uyumunu kapılar; *"zaten pinli mi"* sorusunu **sormaz**. Signal tarafı için bu **davranışsal
olarak** ölçüldü: gerçek `create_trading_signal_revision` komutu aynı normalized revision'ı
ikinci kez pinlerken **reddetmedi**.

## Ölçüm 2 — YAPISAL GERÇEK: kolon **tek değerlidir**, çözüm **ters yöndedir**

`commands/readiness_check.py::_resolve_external` `item.pinned_revision_id`'den satıra gider —
yani *"bu revision'ı taşıyan satır hangisi"*. Pin **satırın üstünde** tek bir kolondur.

> **Sonuç, ve belgenin en önemli cümlesi: aynı batch'i paylaşan iki revision'dan
> ANCAK BİRİ çözülebilir.** Bu bir kodlama hatası değil, kolonun kardinalitesidir.
> Bu yüzden *"kusuru düzelt"* tek başına bir talimat değildir: **hangi revision'ın
> çözüleceğini seçmek bir üründür.**

## Ölçüm 3 — Ulaşılabilirlik ve kullanıcıya görünen sonuç: **ÖLÇÜLDÜ**

Yeni `tests/integration/test_external_import_pin_stability.py` (2 case, gerçek Postgres,
gerçek komutlar) şunu **üretti**:

1. Kompozisyon **READY** — `EXTERNAL_IMPORT_UNRESOLVED` **yok** (vacuity guard).
2. Kullanıcı **yalnız `identity.display_name`'i** değiştirip Save New Revision der. Import'a
   dokunulmaz: aynı source asset, aynı canonical batch.
3. Pin revision N'den **N+1'e taşınır** (DB'den geri okundu).
4. Import **sağlamdır** — `status` ve `accepted_count` değişmemiştir.
5. Mainboard item'ı **K3 gereği repin edilmemiştir**, hâlâ N'e pinlidir.
6. Kompozisyon artık **`not_ready`** ve `EXTERNAL_IMPORT_UNRESOLVED` **BLOCKER** taşır.

**Bir an önce READY olan kompozisyon, hiçbir import bozulmadan, bir görünen ad düzenlemesiyle
BLOCKED oldu.** Aynı dizi Trading Signal yüzeyinde de üretildi.

## Ölçüm 4 — Neden bugüne kadar görülmedi, ve boşluğun **ölçüsü**

Mevcut ikinci-revision case'lerinin hepsi `_SECOND_CSV` ile **farklı** bir batch import eder;
**aynı batch'in yeniden kullanıldığı durum ağaçta hiç koşmuyordu**.

Boşluk *iddia* değil **ölçüldü**: `link_batch_to_revision` set-once yapıldığında (NC-1) en
ilgili iki dosyanın **26 testi de YEŞİL kaldı**. Yani sevk edilen suite, set-once ile bugünkü
davranışı **birbirinden ayırt edemiyordu**.

> Bunun karar açısından anlamı: **hangi seçenek seçilirse seçilsin, mevcut suite bir güvenlik
> ağı sunmaz.** Bu belge indikten sonra ağ, yeni testin kendisidir.

İki modelde de kolonun üstünde `# Set once at Save time` yazar. Bu **bugün tutmuyor**; bir
niyet beyanıdır ve hiçbir şey onu zorlamaz.

## Ölçüm 5 — `G15` ile ilişki: seçeneklerin **ikisi imzalı bir kararı konusuz bırakır**

`G15`/Karar 4 (Seçenek B, **imzalı**, ADIM 120) ters-yön çözümüne **total bir sıra** verdi
(`created_at DESC, <pk> DESC`), çünkü `work_object_revision_id` UNIQUE değildir.

- (a), (b), (c) `G15`'e **dokunmaz** — çözüm yönü aynı kalır.
- (d) ve (e) *"hangi satır kazanır"* sorusunu **konusuz bırakır** (link tablosu revision başına
  tek satır verir; ileri çözüm birincil anahtarla gider). **İmzalı bir kararı konusuz bırakmak
  bir adjudication'dır** ve bir fix slice'ının kararı değildir → §Karar 2.

## Ölçüm 6 — Seçenekler ve **ölçülmüş** bedelleri

| # | Seçenek | Hangi revision çözülür | Migration | `G15`'i konusuz bırakır mı |
|---|---|---|---|---|
| (a) | Statüko | **yeni** (N+1) | yok | hayır |
| (b) | Set-once (koşullu atama) | **eski** (N) | yok | hayır |
| (c) | İkinci pin'i **reddet** | tek pin kalır | yok | hayır |
| (d) | Link tablosu (1:N) | **ikisi de** | **var** | **evet** |
| (e) | Payload'dan **ileri çözüm** | **ikisi de** | yok | **evet** |

**Ek ölçümler:**

- **(b)'nin bedeli türetildi, ayrıca ölçülmedi:** kolon N'de kalır, dolayısıyla N+1'i taşıyan
  satır **yoktur** → kullanıcı item'ı açıkça N+1'e repin ederse (K3'ün istediği eylem) bu kez
  **N+1** `EXTERNAL_IMPORT_UNRESOLVED` verir. Kırılma yok olmaz, **yer değiştirir**.
- **(c) sevk edilmiş bir yolu yasaklar:** import'a dokunmadan revizyon almak imkânsızlaşır,
  kullanıcı yeniden import etmek zorunda kalır. Bunun kabul edilebilir olup olmadığı bir
  **ürün yargısıdır**, ölçüm değil.
- **(d)/(e) tamdır ama pahalıdır.** Satır kopyalama **bilerek tabloya alınmadı**: batch satırı
  `records` / `skipped_rows` / `validation_summary` alanlarını **JSONB olarak kendisi taşır**,
  yani kopyalamak kayıt kümesinin tamamını çoğaltır.
- **(e) için ileri referans ZATEN VAR:** `import_binding.record_batch_revision_id` (Trade Log)
  ve `import_binding.normalized_event_revision_id` (Signal) **zorunlu** config alanlarıdır ve
  config revision'ın payload'udur. Yani (e) yeni veri istemez — yalnız imzalı bir kararı
  konusuz bırakır.

---

## Karar

> Aşağıdaki kutuları **yalnız ürün sahibi / maintainer** doldurur. Ajan dolduramaz
> (`G10`/`G11`/`G12`/`G14`/OD-2 emsali).

### Karar 1 — Aynı batch'i paylaşan revision'lardan hangisi çözülsün?

☐ **(a) STATÜKO — kusur kabul edilir.** Yeni revision çözülür, eski stranded kalır.
*Bedeli:* Ölçüm 3'ün dizisi **kalıcı olur**; kullanıcı bir görünen adı düzenleyerek READY bir
kompozisyonu BLOCKED edebilir ve nedenini gösteren hiçbir şey yoktur.

☑ **(b) SET-ONCE — eski revision kazanır.** `link_*_to_revision` yalnız kolon `None` iken yazar.
*Bedeli:* kırılma N+1'e taşınır (Ölçüm 6). *Lehine:* modellerin **zaten yazdığı** niyeti
(`# Set once at Save time`) doğru yapar ve tek satırdır.

☑ **İmza:** `alimirbagirzade`   ☑ **Tarih:** 2026-09-01 — ürün sahibi şıkkı oturum içinde
seçti, ajan kaydetti (ADIM 66 emsali; kayıt: ADIM 154). Bedel — kırılmanın N+1'e taşınması —
şıkkın kendi metninde yazılıydı ve seçimle birlikte kabul edildi.

☐ **(c) REDDET — zaten pinli bir batch ikinci kez pinlenemez.** `_require_ready_import`'a
fail-closed bir kapı (O-02 zarfı, yeni hata kodu).
*Bedeli:* import'a dokunmadan revizyon almak **yasaklanır**.

☐ **(d) LİNK TABLOSU — ikisi de çözülür.** Migration + `resolve_*` okuyucuları.
*Bedeli:* migration; **ve `G15`/Karar 4'ü konusuz bırakır** → §Karar 2.

☐ **(e) İLERİ ÇÖZÜM — payload'daki referanstan, birincil anahtarla.** Ters kolon çözüm için
gereksizleşir.
*Bedeli:* **`G15`/Karar 4'ü konusuz bırakır** → §Karar 2; ve `_resolve_external`'ın anlamını
değiştirir (bugün *"bu revision'ı taşıyan satır"*, yarın *"bu revision'ın adlandırdığı satır"*).

☐ **Başka:** ______________________________________________

### Karar 2 — (d) veya (e) seçilirse: `G15`/Karar 4'ün konusuz kalması kabul mü?

> **KONUSUZ (2026-09-01):** Karar 1 = (b) seçildi — (d)/(e) seçilmedi, bu kararın ön koşulu
> hiç doğmadı. Kutular **bilerek boş**; boşluk imzasızlık değil, sorunun düşmesidir.

☐ **A — KABUL.** `G15`/Karar 4 tarihsel olur; belgesi `historical` işaretlenir, kaldırılmaz.

☐ **B — KABUL DEĞİL.** (d)/(e) elenir; Karar 1 (a)/(b)/(c) arasından seçilir.

☐ **C — ŞİMDİ ÇÖZME, ADIYLA DEVRET.** (ADIM 129'un `C` kararının biçimi.)

---

## Bu belgenin kapsamadıkları (dürüst sınır)

- **Kusur DÜZELTİLMEDİ.** Bu slice yalnız testi sevk eder. `backend/src`'te **sıfır satır**
  değişti; NC yamaları uygulandı, ölçüldü ve **bayt bayt geri alındı** (`git status` temiz).
- **#854 KAPATILMADI** ve durumu değiştirilmedi — insan kararı.
- **Frontend'e dokunulmadı**, frontend kapıları koşulmadı.
- **Tam suite koşulmadı.** Yerelde 5 dosya / 36 test yeşil (gerçek Postgres, izole DB);
  **geçen sayının ve coverage'ın otoritesi CI'dır.**
- **(b)'nin N+1 bedeli türetildi, deneyle ölçülmedi** (Ölçüm 6'da öyle işaretli).
- Üretimde kaç revision'ın batch paylaştığı **sayılmadı** — bu bir üretim DB sorgusudur ve
  `G15` §Ölçüm 3'ün *"sayılamadı"* sonucuyla aynı sınırda. Karar bu sayı olmadan da verilebilir:
  Ölçüm 3 kusurun **ulaşılabilir** olduğunu tek bir kullanıcı eylemiyle gösterir.
