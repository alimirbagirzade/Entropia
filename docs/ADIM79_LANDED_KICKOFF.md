<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM80_LANDED_KICKOFF.md`'dir.**
> Bu belge yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat
> olabilir. Sayısal gerçekler için otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 79 LANDED — kabul borcu batch 09 (doc 03, backend) · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 79. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

Base **`ff4ed01`** (batch 08'in tepesi; ölçüm anında main `8151cdc`) · alembic head
**`0043_i08_registry_strategy_fks`** · `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** ·
`SHARED_ALLOCATION_STATUS` = **`future_dev`** · migration **YOK** · **ürün kodu değişmedi**.
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**

Tavanlar `partial` **93 → 91**, `debt_class.B` **62 → 60**. Açık kabul borcu:
**A=1 · B=60 · C=6 · D=32 → 99**. Clause `covered` **1019 → 1021**, `uncovered`
**108 → 106**; `total_criteria` **383** (taban).

> **SIRA UYARISI — ZİNCİR ÜÇ SEVİYE DERİN.** #757 (ADIM 75) → #763 (ADIM 76) → bu (ADIM 78).
> **Hiçbiri inmedi.** Alttakilerden biri rebase edilirse bu dal da rebase ister; en alttaki
> merge olana kadar hiçbiri merge edilemez. Sebep: kabul defteri **seri bir kaynak** — baseline
> `supersedes` zinciri bir öncekinin dondurduğu sayıları devralmalı.

## Bu slice'ın öğrettikleri

1. **NEGATİF KONTROLÜN NEDEN kırmızıya döndüğünü OKU — ve gerekirse TESTİ DÜZELT.** `AOS-13.c3`
   ilk yazımda `available_time` taşımıyordu; yetkiyi kaldırınca test kırmızıya döndü ama sebep
   `available_time is required for trading_signal` idi, yani çağrı **yetki kapısını geçmiş** ve
   doğrulamaya takılmıştı. Red **yetkilendirmeye atfedilemiyordu**. Alan eklendi, kontrol temiz
   oldu (`DID NOT RAISE AccessDeniedError`). **Confounded bir red, red değildir.**
2. **"Tek fonksiyon iki kind'a hizmet ediyor" kardeşi ödünç almak için gerekçe değildir.**
   `AOS-05.c1` bilerek ayrı pinlendi; negatif kontrol haklılığını gösterdi — tek kind'a özel bir
   sapma **kardeşi yeşil bırakıp** bu satırı kırıyor.
3. **YANLIŞLANAMAZ clause'lar bir DESEN oldu, tek tek vaka değil.** Artık dördü var
   (`TS-02.c2`, `PC-02.c2`, `AOS-04.c2`, `AOS-06.c2`) ve hepsi aynı kökten: **transient /
   var olmayan bir yüzey** hakkında bir yokluk iddiası. `AOS-06.c2` en saf hâli — `discard`
   ağaçta **hiç yok**, yalnız yokluğu tarif eden bir yorum var. Bunlar artık bir **adjudication
   kalemi**, slice işi değil.
4. **Fixture'ı commit et, sonra rollback'li reddi sür.** İlk koşuda `session.rollback()` sadece
   flush edilmiş work object'i de geri aldı ve komut `WorkObjectNotFoundError` verdi. İki ardışık
   `pytest.raises` sürüyorsan kurulum **commit** edilmiş olmalı.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Düğüm / sembol | Nerede | Ne işe yarar |
|---|---|---|
| `SUPERVISOR` aktörü + `super_h` principal | `tests/integration/test_mainboard_authz.py` | rol-spesifik yetki reddini **mainboard** düzleminde sürmek |
| `_create_work_object(..., object_kind=...)` | aynı dosya | artık **external** kind'lar da kurulabiliyor (varsayılan STRATEGY, mevcut çağıranlar etkilenmedi) |
| `test_supervisor_cannot_edit_or_delete_a_foreign_external_object` | aynı dosya | iki fiil × iki kind parametrizasyonu + **kalıcı red** doğrulaması |
| `test_external_trade_log_draft_is_transient` | `tests/contract/test_mainboard_contract.py` | per-kind transient-draft sözleşmesi |

## Açık bulgular — bunları kapatmaya çalışma (ON ÜÇ)

`TL-11.c3`, `TL-16`, `TL-01.c4`, `RD-01.c4`, `RD-05.c5`, `RD-12.c4`, `RD-13.c4`,
`PC-20.c3`, `PC-02.c2`, `TS-07.c2`, `TS-02.c2`, **`AOS-04.c2`**, **`AOS-06.c2`**.

**Dördü aynı şekle sahip** (`TS-02.c2`, `PC-02.c2`, `AOS-04.c2`, `AOS-06.c2`): transient ya da
hiç var olmayan bir yüzey hakkında **yanlışlanamaz** yokluk iddiaları. Bir sonraki slice bunları
tek tek yeniden ölçmesin — **toplu bir adjudication** öner.

## Sıradaki tasarım işaretleri

- **`AOS-01.c2` HAZIR BEKLİYOR ve tek satırlık bir frontend partisi.** Chooser seçimleri **link**
  olarak render ediliyor (`OutsourceSignal.tsx:114`), yani klavye pariteliği native. Assertion:
  her seçim href'li, klavyeyle işletilebilir bir link. Negatif kontrol **gerçek**: link'i
  `div onClick` yapmak testi kırmızıya çevirir. Doc 03'ü bitirir.
- **Sınıf B'de 60 kriter kaldı.** Doc 07 ve doc 04 tükendi, doc 03'ten yalnız `AOS-01.c2` kaldı.
  Kalan yoğun belgeler: **doc 05** (TL, 8 — ama üçü şüpheli, gerçekte **5**), **doc 02** (AT, 5),
  **doc 18** (AL, 5).
- **A-08 tek blocker**; yalnız insan denetimi kapatır (#514).
- **G9/G13 İMZALI** (#753) — `C2` imzasız kapıların arkasında değil.

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu sınıf B, batch 10
TEK SLICE

ROL: Entropia V18 Principal Engineer. Yalnız bu slice.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

TABAN — ÖNCE ZİNCİRİ ÖLÇ
  Üç PR yığılı ve hiçbiri inmemiş olabilir: #768 (ADIM 78 + 78) tek PR. Her birinin state/merged durumunu API'den OKU.
  - Hepsi indiyse: main'den dallan.
  - Biri açıksa: EN ÜSTTEKİ açık dalın üstüne YIĞ.
  Numarayı `grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -1` ile ÖĞREN; merge edilmiş ad
  kazanır ve bu dalgada numara ZATEN İKİ KEZ taşındı.

ÖNERİLEN PARTİ: doc 03 FRONTEND — tek satır, `AOS-01.c2` (chooser klavye paritesi).
  Seçimler link olarak render ediliyor; assertion "her seçim href'li, klavyeyle işletilebilir
  bir link", negatif kontrol "link -> div onClick". Doc 03'ü BİTİRİR.
  Sonrası: doc 02 (AT, 5) ya da doc 18 (AL, 5). Doc 05'e girersen üç şüpheli satırı SAYMA.

ÖN KOŞUL — ÖLÇEREK SEÇ
  Her aday için SIRAYLA:
    (a) kriterin SON açık clause'u mu? değilse tavan İNMEZ;
    (b) davranış sevk edilmiş mi? grep ile doğrula;
    (c) durum kurulabilir mi?
    (d) HANGİ TEK DEĞİŞİKLİK bu testi kırar? cevap yoksa clause YANLIŞLANAMAZ — yeşil bir
        test kapsamak değil İŞARETLEMEK olur.
  (b)/(c)/(d)'den biri düşerse: bulguyu `notes`'a ÖLÇÜMÜYLE yaz, YENİDEN SINIFLANDIRMA.
  ON ÜÇ açık bulgu var; dördü (TS-02.c2, PC-02.c2, AOS-04.c2, AOS-06.c2) aynı yanlışlanamaz
  şekle sahip — TOPLU ADJUDICATION öner, tek tek yeniden ölçme.

YAPILACAK
  Her clause için testi yaz ve NEGATİF KONTROLDEN geçir. Kırmızının HANGİ ASSERTION'da
  olduğunu OKU: confounded bir kırmızı (ör. yetki yerine doğrulama hatası) hiçbir şey
  kanıtlamaz — testi düzelt, kontrolü tekrarla (ADIM 79 dersi).
  Frontend düğüm id'si `::` DEĞİL ` > ` ile yazılır.
  Rollback'li redlerde fixture'ı ÖNCE commit et.

RATCHET
  Tavanları ÖLÇÜLEN değere İNDİR (partial 91 / B 60 taban). total_criteria = 383 TABAN.
  YAML notes'u TIRNAKLA (':' içeren metin plain scalar'ı bozar).
  Clause toplamlarını --report'tan oku. Sonra --write-ledger + repository_facts.

TEST
  repository_facts'i TAM SUITE KOŞMADAN ÖNCE tazele (ADIM 73 dersi).
  cd backend && uv run pytest -q      (alt kümede --no-cov)
  `cmd | tail` KULLANMA — exit code tail'in olur (ADIM 76'da ruff format böyle kaçtı).

COMMIT / PR
  DAL: test/closure-acceptance-batch-10
  commit: test(closure-acceptance): <kapatilan clause'lar>
  AI ATTRIBUTION YOK. Draft PR (yığılıysa base'i açık dala ver), MERGE ETME.

FINAL RESPONSE
  Kapanan clause'lar + inen tavanlar + KAYDEDİLEN BULGULAR + kapıların GERÇEK sayıları +
  dürüst sınırlar. DUR.
```
