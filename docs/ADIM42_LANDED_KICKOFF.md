<!-- doc-status: historical -->
> **SUPERSEDED by `docs/ADIM43_LANDED_KICKOFF.md` (ADIM 43, 2026-08-12).** Bu belge
> yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`.
> **Hâlâ geçerli olan kısım:** P1-Gate3'ün A/B/C/D borç sınıflandırması, ratchet'i ve
> üretilmiş defteri — ADIM 43 onlara dokunmadı.

# ADIM 42 landed — kickoff / devam tohumu

> **ADIM 42 = RC §6.7 / P1-Gate3.** Kabul kriteri kapsamı **ölçüldü, sınıflandırıldı,
> ratchet'lendi, üç grup pinlendi.** 139 kalem **kapatılmadı** — kapatmak bu slice'ın işi
> değildi. **P1-Gate3 KAPANMADI**, ele alınabilir hale geldi.

---

## Neredeyiz

| | |
|---|---|
| Rapor kalemi | **P1-Gate3** — *"8 uncovered + 131 partial (kapı yeşil sayıyor)"* |
| Sonuç | Sayılar **bayat değildi**; kalem *sayı yanlış* diye değil **sayı anlamsız** diye açıktı |
| Yeni taban | covered **234** · partial **126** · uncovered **8** (383 kriter / 1175 clause) |
| Açık borç | **134 kalem**, sınıflı: **A=1 · B=95 · C=6 · D=32** |
| Kapı | `acceptance_semantic_scan.py --report --ratchet`, `ci.yml`'da, **negatifi kanıtlı** |
| Verdict | **BLOCKED** (değişmedi), blocker sayısı **üç** (değişmedi) |

---

## Bu slice'ın bıraktıkları — reuse anchor'ları (tam sembol adlarıyla)

| Anchor | Ne işe yarar |
|---|---|
| `docs/audit/acceptance_semantic_scan.py::DEBT_CLASSES` | A/B/C/D sözlüğü + her sınıfın **kim kapatır** tanımı |
| `…::STATUSES_REQUIRING_DEBT_CLASS` | Yalnız `partial`/`uncovered` sınıflanır |
| `…::measured_counts` | Bugünkü borcu **baseline'ın kendi şeklinde** üretir (tavan yazarken bunu kullan) |
| `…::ratchet` | Tavan karşılaştırması; `(ok, lines)` döner, tavan altına düşünce sıkılaştırılmış bloğu basar |
| `…::ledger` / `…::LEDGER_PREAMBLE` | Defteri **üretir**; bayatlığı `test_the_debt_ledger_is_not_stale` yakalar |
| `docs/audit/acceptance_coverage_baseline.json` | Dondurulmuş tavan + `provenance` + `adjudication` |
| `docs/audit/acceptance_coverage_debt_ledger.md` | **ÜRETİLMİŞ** sıralı defter — planlama buradan yapılır |
| `backend/tests/unit/test_acceptance_semantic_map.py::_open_record` | Sentetik "gerçek borç" kaydı; yeni kapı kuralı eklerken bunu perturbe et |
| `…::test_the_frozen_ceiling_leaves_no_headroom` | Tavanın ölçüme **eşit** kalmasını kilitler |
| `backend/tests/integration/test_backtest_persistence.py::test_active_run_blocks_work_object_delete` | **O-31 pin'i** — wire kodu + 409 + sıfır TrashEntry |
| `backend/tests/integration/test_trade_log_persistence.py::test_soft_delete_removes_item_from_projection` | **K-06 pin'i** — trash + audit + outbox |

---

## Pazarlıksız kurallar (bu slice'ın koyduğu)

1. **Yeni `partial`/`uncovered` kriter `debt_class` SİZ vermeden geçmez.** Kapı
   `DEBT_CLASS_REQUIRED` ile kırmızıya döner. Sınıfsız bir açık kriter, "131 partial"ı
   planlanamaz yapan tam olarak o şeydir.
2. **Tavanı yükselterek CI'ı yeşile çevirme.** Ya kriteri kapat (onu **assert eden** bir
   test node'u göster), ya sınıfını `notes`'ta gerekçelendirip defterde adjudicate et.
3. **Pay bırakma.** Ölçümün üstünde bir tavan, bir sonraki kanıtsız kriteri sessizce
   lisanslar; bu testle kilitli.
4. **Sınıf C'nin tavanını sıfıra indirmeye çalışma.** Bir belge cümlesini tatmin etmek için
   ürün icat etmek demektir.
5. **Sınıf D'yi test slice'ına bütçeleme.** 32 kalemin hiçbiri testle kapanmaz.

---

## Sıradaki iş — defterden okunur, buradan sayılmaz

Planlama sırası **A (1) → B (95) → D (32, ürün) ; C (6) hiç kapatılmaz.**
Kalemleri `docs/audit/acceptance_coverage_debt_ledger.md`'den al — **bu belgeye kopyalama**,
bayatlar.

**Sınıf D'nin ürün kararı isteyen alt kümesi (PO'ya SORULMADI, deftere kaydedildi):**

* `RD-02` — doc 12 §14 *"available time Fixed delay; delay 2 minutes"* diyor; form
  `same_as_event_time` ile açılıyor ve delay input'u hiç render etmiyor. **Doc mu değişecek,
  form mu?**
* `RD-03` — doc 12 §14 on iki alanın sunucu tarafında zorunlu olmasını istiyor;
  `CreateDatasetRequest` yalnız üçünü zorunlu kılıyor. **Şema mı sıkılacak, satır mı daralacak?**
* `AM-11` — `booking.py::close_position`, `is_full` fark etmeksizin `stops_hit` artırıyor;
  kriter kısmi stop bacağının Total Stops'a **girmemesini** istiyor. **Uygulama kriterle
  çelişiyor gibi duruyor** — ürün/mühendislik kararı, test kararı değil.
* `AOS-02` — spec adlandırılmış bir UI mesajı istiyor; sevk edilen chooser'da o durumu
  **kurmak imkânsız**. **Mesaj mı eklenecek, satır mı yeniden yazılacak?**

---

## Dürüst sınırlar (devralan bunları bilmeli)

* **134 açık kriterin hiçbiri kapatılmadı.**
* Sınıflandırma her kaydın **kendi `notes` gerekçesinden** okundu; 134 test gövdesi tek tek
  yeniden **okunmadı** (bu, 139 kalemi kapatmak olurdu). Bir yanlış sınıflandırma mümkündür;
  **`notes` otoritedir**, bu defter değil.
* `acceptance_id_scan.py` (zayıf kardeş tarayıcı) ve Master doc'un 21 modül-düzeyi kabul
  tablosu **hâlâ kapsam dışı** — haritanın kendi §Scope boundary'si bunu söylüyor.
* Brief'in `K-06 = upload dosya-tipi kapısı` tanımı **yanlıştı** (o **K-07**). K-07 ölçüldü:
  **zaten pinli**, beş sayfa taksonomisi de assert ediliyor.

---

## Çalışma yöntemi (işe yarayan)

1. **Önce ölç, sonra inan.** Rapor P1-Gate3'te iki kez yanılmıştı (`AT-04` "pinsiz" değil
   *uygulanmamış*tı; `K-06` yanlış tarif edilmişti). Her iddiayı `grep`'le doğrula.
2. **Taksonomiyi veriye uydur, veriyi taksonomiye değil.** Üç sınıf yetmedi; dördüncüyü
   eklemek "brief'e uymamak" değil, dürüst olmaktı.
3. **Kapıyı kırmızıya döndürmeden bitirme.** Negatif kanıt olmadan bir ratchet dekordur.
4. **Sayıyı düzyazıya gömme.** Tavan bir dosyada, defter üretilmiş, ikisi de testle kapılı.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 43: RC §6.7 — sıradaki kalem

BASE: origin/main (DOĞRULA — ADIM 42 / P1-Gate3 merge olmuş OLMALI; olmadıysa DUR)

OTURUM BAŞLANGICI
  git fetch && git log --oneline origin/main -6 && gh pr list --state all
  Oku: docs/ADIM42_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md (§ADIM 42 landed + Next)
       → docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6 + §6.7.10
       → docs/audit/acceptance_coverage_debt_ledger.md (defter)

DURUM (ADIM 42 sonrası)
  · Kabul kapsamı: 383 kriter · covered 234 · partial 126 · uncovered 8
  · Açık borç 134 kalem, sınıflı: A=1 · B=95 · C=6 · D=32
  · Ratchet CI'da (`--ratchet`), paysız, negatifi kanıtlı
  · P1-Gate3 KAPANMADI · blocker üç · verdict BLOCKED

AÇIK KALEMLER (rapor §6.7 tablosundan — hangisini alacağını PO/insan seçer)
  · P11-1 branch protection — AGENT İŞİ DEĞİL (repo ayarı)
  · P11-6b · P11-8 (Lighthouse) · P10-7 (latency ratio gate)
  · P8-B2'nin PO yarısı · P8-B3b · P10-B3/B4/B5
  · A-08 ekran okuyucu denetimi — İNSAN İŞİ, agent kapatamaz
  · P1-Gate3 backlog'u: A(1) → B(95) → D(32, ürün). C(6) hiç kapatılmaz.

TAVİZ VERİLEMEZ
  · Yeni partial/uncovered kriter eklersen `debt_class` ZORUNLU.
  · Ratchet tavanını YÜKSELTME. Kriteri kapat ya da sınıfını gerekçelendir.
  · Sınıf D'yi test slice'ına bütçeleme — hiçbir test kapatamaz.
  · Sınıf C'nin tavanını sıfıra indirme.
  · "READY" YAZMA · blocker sayısını düşürme · yeşile zorlama YOK.

ÖLÇÜM TUZAKLARI
  · pytest'i | tail'e BORULAMA (exit code tail'in olur) · alt kümede --no-cov
  · TEST_DATABASE_URL ile izole DB, sürücü postgresql+asyncpg://
  · yeni/değişen CI job'ının GERÇEKTEN koştuğunu job LOG'undan doğrula
  · docs PR'ı öncesi: git diff origin/main -- docs/PROJECT_HISTORY.md | grep '^-' → BOŞ

KAPANIŞ
  · CLAUDE.md §Session CLOSING ritüelinin 6 maddesi
  · cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
