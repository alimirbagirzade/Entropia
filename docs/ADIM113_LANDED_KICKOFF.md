<!-- doc-status: current -->

# ADIM 113 landed — sınıf B tükendi; sıradaki slice bir PARTİ OLAMAZ

> Bu belge **canlı seed**'dir. Bir sonraki oturum buradan devam eder.
> Otorite sırası değişmedi: bu belge → `docs/STAGE2_HANDOFF.md` → `docs/STAGE_BUILD_PLAN.md`
> → `docs/spec/NN_*` → `docs/PROJECT_HISTORY.md` §ADIM 113.

## Neredeyiz

`main` = ADIM 113 (bu slice). alembic head `0043_i08_registry_strategy_fks`, migration yok;
`ENGINE_VERSION` / OpenAPI / `SHARED_ALLOCATION_STATUS` (`future_dev`) değişmedi.
Kabul borcu tavanı **54 partial / 6 uncovered · A1 B21 C6 D32**, açık borç **60**.
Blocker **1 — yalnız A-08**, verdict **BLOCKED**.

## Bu slice ne bıraktı

**Bir kapı değil, bir sınır.** Kabul borcu partileri ADIM 48'den ADIM 110'a kadar sınıf-B
satırları kapattı. **O kaynak bitti:** açık 21 sınıf-B satırın **21'inin de** kayıtlı bir
bulgusu var, yani hiçbiri *"davranış sevk edilmiş, eksik olan assertion"* tanımına uymuyor.
Bir sonraki oturum **`--report` açıp parti seçmeye çalışmasın** — çıkacak liste kapatılabilir
satır listesi değil.

**Defter artık bunu SÖYLÜYOR.** Altı satırın bulgusu prozada kilitliydi ve defterin `Why`
sütununa hiç ulaşmıyordu; `notes` düzlemine yazıldı. Ölçüm: bulgu işareti taşıyan satır
**15 → 21**, "temiz" görünen **0**.

### Yeniden kullanım çapaları (birebir adlar)

| Ne | Nerede |
|---|---|
| Sınıf-B tükenme ölçümü | `docs/PROJECT_HISTORY.md` §ADIM 113 tablosu |
| Altı düzeltilmiş `notes` | `docs/audit/acceptance_semantic_map.yaml` → `CP-03` `MB-22` `RF-08` `TL-01` `TR-07` `UM-15`, hepsi `FINDING (ADIM …)` ile başlar |
| Üretilmiş defter | `docs/audit/acceptance_coverage_debt_ledger.md` (`Why` sütunu artık bulguyla başlar) |
| Tavan | `docs/audit/acceptance_coverage_baseline.json` — **EL DEĞMEDİ** |
| `CP-03.c4` ölçümü | `frontend/src/components/AddPackagePopover.tsx:127` + `frontend/src/lib/strategy.ts:371` |

## Sıradaki oturum için — dört yol, hiçbiri "parti" değil

1. **İMZALAR (handoff'un kendi `## Next:`'i).** `G8` (#559) · `G14` (#544) · Karar 1 (komisyon
   tabanı) → sonra `C6`. **Kod değil, insan kararı.** Sıra ve gerekçe:
   `docs/audit/final_closure_delta_audit_2026-08-25.md` §10.
2. **`B → D` yeniden sınıflandırma.** 21 satırın gerçek sınıfına taşınması defterin *"bunu bir
   test slice'ı kapatır"* bütçesini düzeltir — ama **D tavanını YÜKSELTİR**, yani bir
   **adjudication**. İmza ister; bir slice kendi başına yapamaz.
3. **Ölçülmüş kusurları kapatmak (ÜRÜN KODU).** Üçü aynı şekle sahip ve üçü de kayıtlı:
   `UM-15.c3` (ADIM 110) · `CP-03.c4` + bayat-hata sızıntısı (ADIM 113) · ADIM 87'nin ikizi —
   hepsi **`onSuccess`-only**, hata yolunda invalidation/temizlik yok. Bir düzeltme partisi
   üçünü birden alabilir; presentation-only sınırının **dışında**, o yüzden kapsamı önce
   kullanıcıyla netleştir.
4. **A-08** (tek blocker). Defter **2/184** hücre · **0/10** akış · SR-1 hiç başlamadı · **0/4**.
   İlerlemesi bir **insanın** ekran okuyucuyla oturmasını ister.

## Tuzaklar — bu slice'ta ölçüldü

- **`notes` taraması TEK BAŞINA parti seçmeye yetmez.** Bu oturum tam olarak öyle yanıldı:
  *"7 temiz aday"* çıktı, altısı kayıtlı bulguydu. Artık `notes` düzeltildi, ama kural kalıcı:
  **bir satırı aday saymadan önce `CLAUDE.md` + `PROJECT_HISTORY`'de id'sini ara.**
- **Defterin `Why` sütunu `notes`'u KESER.** Bir nota eklenen açıklama **başa** yazılmazsa o
  sütuna hiç ulaşmaz. İlk deneme sona yazdı ve görünmedi.
- **Map'te iki ayrı `notes` skaler stili var** — çoğu tek tırnaklı, `RF-08`/`UM-15` tırnaksız çok
  satırlı. Tek stil varsayan bir betik sessizce **iki satırı atlar**; yazmadan önce assert et.
- **`--check-generated` map'i elle düzenleyince kırmızı verir** — `--write-report` ve
  `--write-ledger`'ı birlikte koştur, sonra `--ratchet`'ı yeniden oku.
- **Ratchet'ı elle aritmetikle taşıma** — merged ağaçta taze `--report`'tan oku (ADIM 93/98/100).

## Paste-ready resume prompt

```
Entropia — ADIM 114. ÖNCE §Session START protokolü: git fetch, git log --oneline origin/main -6,
açık PR'ları listele. Otorite sırası: docs/ADIM113_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md
→ docs/STAGE_BUILD_PLAN.md → docs/spec/NN_* → docs/PROJECT_HISTORY.md §ADIM 113.

BİL: kabul borcu partisi ARTIK KURULAMAZ. Açık 21 sınıf-B satırın 21'inin de kayıtlı bulgusu
var (ADIM 113'te ölçüldü); sınıf B, bir test slice'ının sahip olduğu tek sınıftı ve tükendi.
--report açıp aday arama — çıkan liste kapatılabilir satır listesi DEĞİL.

Dört yol var, hiçbiri parti değil: (1) İMZALAR — G8 #559, G14 #544, Karar 1 komisyon tabanı,
sonra C6 (insan kararı, kod değil); (2) B→D yeniden sınıflandırma (D tavanını yükseltir =
adjudication, imza ister); (3) onSuccess-only kusur ailesini kapatan bir ÜRÜN partisi
(UM-15.c3 + CP-03.c4 + bayat-hata sızıntısı — presentation-only sınırının dışında, kapsamı
önce kullanıcıyla netleştir); (4) A-08 (tek blocker, 2/184 · 0/10 · 0/4, insan gerektirir).
HANGİSİ olduğunu kullanıcıya sor; kendi başına seçme.

Tavana DOKUNMA: 54/6 · A1 B21 C6 D32, acceptance_coverage_baseline.json el değmez.
Kapanışta: PROJECT_HISTORY §ADIM 114 (dosya SONUNA) · STAGE2_HANDOFF ## Stage 114 (son
## Next: başlığından HEMEN ÖNCE, başlığı DEĞİŞTİRME) · CLAUDE.md §Current position 5-6 satır
+ ADIM 113 bloğunu "Öncesinde" yap · docs/ADIM114_LANDED_KICKOFF.md yaz ve ADIM113'ü
historical yap · node scripts/memory_index.mjs --sync --only adim-114 + --check.
Kapılar: bash scripts/hook-guard-proof.sh (23/23) · cd scripts && uv run --project ../backend
python generate_repository_facts.py --root .. --check · uv run --project backend python
docs/audit/acceptance_semantic_scan.py --report --check-generated --ratchet ·
git diff origin/main -- docs/PROJECT_HISTORY.md docs/STAGE2_HANDOFF.md | grep '^-## ' (boş).
A08_COMPLETE mayını: A-08 ile Complete/PASS/Done/tamamlan/kapandı AYNI SATIRDA 80 karakter
içinde geçmesin (kapsam CLAUDE.md, STAGE2_HANDOFF, README, CODEMAPS) — kuralı değil PROZAYI
düzelt, satırı ayır, kelimeyi koru.
Dal docs/stage-114-landed → commit → push → PR. Self-merge BLOKLU, merge'ü kullanıcı yapar.
Push komutunun dizesinde "main" kelimesi GEÇMESİN (guard tüm dizede desen arar).
```
