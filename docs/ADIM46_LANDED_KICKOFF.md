<!-- doc-status: historical -->
> **SUPERSEDED — ADIM 47 (2026-08-12).** Canlı kickoff artık
> `docs/ADIM47_LANDED_KICKOFF.md`. Aşağısı ADIM 46 kapanışındaki durumu kaydeder;
> sayıları ve "sıradaki iş" maddeleri bayat olabilir.

# ADIM 46 LANDED — RC §6.6'nın iki canlı N+1'i kapandı (#617 + #618, PR #681)

## Nerede duruyoruz

RC readiness raporunun **§6.6** kalemlerinden **iki KOD kalemi kapandı**. Blocker sayısı
**DEĞİŞMEDİ (1)**, verdict **BLOCKED**. Geriye kalan tek blocker **A-08**'dir ve bu slice
ona **dokunmadı**.

| kalem | önce (n=1 → n=11) | sonra | slope |
|---|---|---|---|
| **#617** `readiness_check.market_data_leg` | 2 → **12** | 2 → **2** | **1.0 → 0** |
| **#618** `dependency_pins.ensure_pinned_resolvers_active` | 2 → **22** | 2 → **2** | **2.0 → 0** |

## Bu slice'ın yöntemi — kopyalanabilir

**1. Kusuru yeniden üretmeden kod yazma.** Rapor 2026-08-07'den. Kod yazılmadan önce
`c931063` üzerinde **mevcut** kapıyla yeniden ölçüldü
(`tests/integration/test_query_budgets.py`); yeni bir ölçüm aracı **icat edilmedi**.
Sayılar birebir çıktı → kusur canlıydı.

**2. Kapı sessizken ham sayıyı nasıl alırsın.** `test_query_budgets.py` yalnız bütçenin
**altına** inildiğinde `came in under budget` satırı basar; bütçeye eşitken sessizdir. Ham
sayı için tavanları geçici yükselten **salt-okuma bir pytest plugin'i** kullanıldı
(scratchpad'de, repo'ya girmedi). `query_budgets.json`'ı "ölçmek için" gevşetme —
plugin'le oku.

**3. Sorgu sayısı davranışı kanıtlamaz.** Ratchet N+1'i durdurur; batch'in **doğru cevabı
verdiğini** söylemez. Bu yüzden eşdeğerlik ayrı dosyada.

**4. Negatifi kanıtla, iki kez.** (a) `src/` geri alınınca ratchet kırmızı;
(b) batch'i bilerek bozunca (mutasyon) eşdeğerlik testleri kırmızı. İkisi de yapıldı.

## Bu slice'ın bıraktıkları — REUSE anchor'ları (tam sembol adlarıyla)

| sembol | ne işe yarar |
|---|---|
| `repositories/market_data.py::get_dataset_roots` | Root'ları tek `IN()` ile çözer; **`entity_type` kapısı SQL'de** — yok olan da market olmayan da map'te yok |
| `repositories/esp.py::get_registry_by_keys` | registry entry'lerini tek `IN()` ile çözer; `canonical_key` UNIQUE |
| `queries/dependency_pins.py::_prefetch` | iki batch'i **sırayla** kuran TEK yer |
| `queries/dependency_pins.py::_pin_defect` | artık **saf** — session almaz, iki map alır |
| `commands/readiness_check.py::_resolve_market_data_issues` | iki batch, sıfır döngü-içi await |
| `tests/integration/test_batched_dereference_equivalence.py` | 13 test; yeni bir batch dereference eklersen buraya yaz |

## Pazarlıksız kurallar (bu slice'tan çıkan)

- **`_prefetch`'in sırasını bozma.** `embedded_revision_id` vermeyen bir ref, entry'sinin
  `trusted_active_revision_id`'sine düşer → revizyon id'leri **ancak registry map'inden
  sonra** bilinir. Sırayı ters çevirmek fallback'i sessizce öldürür ve
  `test_a_ref_naming_no_revision_falls_back_to_the_trusted_active_one` kırmızıya döner.
- **Anahtarı bulunmayan ref revizyon batch'ine katkı vermez.** Zaten `key_not_found`;
  fallback ettirmek alakasız bir satırı batch'e sokar.
- **Batch'ten `entity_type` kapısını düşürme.** Root'un market dataset olması bir
  fail-closed koşuludur, filtre değil.
- **`per_item: 0`'ı yükseltme.** N+1 geri geldiyse batch'i onar; tavanı değil.
- **Yeni bir okuma yüzeyi eklerken** döngü içine `session.get` koyma — batch karşılığını
  yaz (`get_revisions` / `get_dataset_roots` / `get_registry_by_keys` deseni).

## Bilinen sınırlar — bu slice bunları KAPATMADI

- **A-08 / #514** — ekran okuyucu denetimi **yapılmadı**, defter **boş** (0/4). Tek kalan
  blocker. **İnsan kapısı.**
- **#558 / #559** — ürün kararı; strict `xfail` yerinde.
- **P11-1** — branch protection yok → hiçbir kapı merge'i **mekanik** durduramaz. Repo
  ayarı, **insan kararı**.
- **P11-6b, P8-B2'nin PO yarısı, P8-B3b, P4-3, P10-B2'nin aşım davranışı, P10-B6** — açık.
- **PR B** (`ItemParticipant`) — ADR §16 insan kapısının arkasında, dokunulmadı.

## Bir tuzak — tekrarlama

Mutasyon kanıtından sonra mutantları `git checkout -- <dosya>` ile geri alırken **aynı
dosyalardaki commit edilmemiş düzeltmeler de silindi**. Sembol `grep -c`'siyle yakalandı,
iş yeniden uygulandı. **Mutasyon denemesinden ÖNCE commit et** (ya da mutantı `git stash`
ile ayır) — `checkout --` staged olmayan her şeyi götürür.

Bir diğeri: `cd backend && …` zincirinde `cd` başarısız olursa (zaten backend'deysen)
**zincirin geri kalanı hiç koşmaz**; ardından `… | tail` yazarsan exit code `tail`'in olur
ve başarısızlık **sessizce yeşil** görünür. `pwd` yaz, çıktıyı dosyaya al, `$?`'i ayrı oku.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 47

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — git fetch && git log --oneline origin/main -6)
Son landed: ADIM 46 — RC §6.6'nın iki N+1'i (#617 + #618), PR #681.

NEREDE DURUYORUZ
  · Blocker sayısı 1, verdict BLOCKED. Tek kalan blocker = A-08.
  · §6.6'nın #617/#618 satırlarının KOD yarısı kapandı; #514/#558/#559 açık.
  · query_budgets.json'da iki yüzey de per_item 0 — bu bir ratchet, tavanı yükseltme.

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT)
  · git fetch; git log --oneline origin/main -6; gh pr list --state all
  · docs/ADIM46_LANDED_KICKOFF.md (bu dosya) + docs/STAGE2_HANDOFF.md §Next
  · docs/generated/repository_facts.md — SAYISAL OTORİTE burasıdır

BU ADIMIN KONUSU — biri seçilecek, HEPSİ DEĞİL
  (a) A-08 ekran okuyucu denetimi — YALNIZ insan koşabilir; agent hazırlığı bitti
      (scripts/a11y-audit-stack.sh 9/9, runbook yazılı, defter boş). Agent
      defteri DOLDURAMAZ, #514'ü KAPATAMAZ.
  (b) RC §6.7'nin açık kalemleri: P11-6b · P8-B3b · P4-3 · P10-B6 ·
      P10-B2'nin aşım davranışı (PO kararı) · P8-B2'nin PO yarısı (PO kararı)
  (c) PR B — ItemParticipant adaptörü + jobs/backtest_engine.py call site.
      ADR §16 insan kapısı + ADR amendment'ı GEREKİR; o kapıdan geçmeden başlama.

YÖNTEM (ADIM 46'dan devral)
  · Kusuru YENİDEN ÜRETMEDEN kod yazma. Rapor sayısı bayat olabilir — bugün ölç.
  · Mevcut kapıyı kullan, yeni ölçüm aracı icat etme.
  · Kapı sayı basmıyorsa tavanı gevşetme; salt-okuma bir pytest plugin'iyle oku.
  · Her düzeltme kendi tabanını SIKIŞTIRARAK gelir (ratchet idiyomu).
  · Negatifi kanıtla: kapı, düzeltme geri alınınca kırmızıya dönmeli.
  · Sorgu/kapsam sayısı DAVRANIŞI KANITLAMAZ — eşdeğerliği ayrı test et,
    ve o testi MUTASYONLA sına.

TAVİZ VERİLEMEZ
  · DAVRANIŞ DEĞİŞMEZ; hata zarfı tek şekildir (O-02: shared/responses.py::ErrorBody).
  · Historical Result/manifest canlı root veya live registry join'iyle YENİDEN
    YORUMLANMAZ.
  · ENGINE_VERSION'a dokunma; OpenAPI değişecekse ayrı karar.
  · Yeşile zorlama YOK. "READY" YAZMA — verdict BLOCKED.
  · Satır numarası yazma, sembol adı kullan.

TUZAKLAR
  · pytest'i | tail'e BORULAMA — exit code tail'in olur. Çıktıyı dosyaya yaz, $?'i ayrı oku.
  · `cd X && …` zincirinde cd başarısız olursa gerisi hiç koşmaz — pwd ile doğrula.
  · Alt küme koşarken --no-cov EKLE; tam suite TEK çağrıda, ortada öldürme.
  · TEST_DATABASE_URL ile izole DB; sürücü postgresql+asyncpg://
  · git checkout -- <dosya> commit EDİLMEMİŞ işi de siler — mutasyon denemesinden
    önce commit et.
  · docs PR'ı öncesi: git diff origin/main -- docs/ | grep '^-## ' → BOŞ olmalı.
  · CI job'ının GERÇEKTEN koştuğunu job log'undan doğrula.

KAPANIŞ
  · CLAUDE.md §Session CLOSING ritüelinin 6 maddesi.
  · cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
