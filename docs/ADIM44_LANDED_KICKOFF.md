<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat olabilir. Güncel otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`.

# ADIM 44 landed — RC blocker 4 kapandı, blocker 1 koşulabilir hâle geldi

**Base:** `e719af1` · **Branch:** `release/rc-blocker4-and-a08-readiness` ·
**Tarih:** 2026-08-12 · **Migration YOK** · `ENGINE_VERSION` değişmedi ·
**bağımlılık sürümü değişmedi, downgrade yok.**

---

## 1. Nerede olduğumuz

RC blocker sayısı **4 → 2**. Kalanlar: **(1)** A-08 insan denetimi, **(2)** kabul
akışlarının CI kapısı olmaması. **Verdict BLOCKED.**

| Blocker | Durum |
|---|---|
| (1) `A-08-HUMAN-GATE-UNMET` | **AÇIK** — çıkış kriterleri 0/4. ADIM 44 yalnız **hazırlık** engellerini kaldırdı |
| (2) Kabul akışları | **AÇIK** — `flows` hâlâ CI kapısı değil |
| ~~(3)~~ Alertmanager | ~~KAPANDI ADIM 31~~ |
| ~~(4)~~ react-router freeze | **KAPANDI ADIM 44** — imzayla değil, **kaldırmayla** |

## 2. Bu slice'ın bıraktığı yeniden kullanım çıpaları (tam sembol adlarıyla)

| Sembol / yol | Ne yapar |
|---|---|
| `scripts/lib/security-allowlist.mjs::loadAllowlist` | `.github/security-allowlist.json`'ı okur + doğrular; `{scopes, entries}` döner. Bozuk allowlist **kapıyı atlatmaz, düşürür** |
| `…::enforceExpiry` | Süresi geçmiş kayıt → `exit 1`; >`MAX_EXCEPTION_DAYS` (90) → WARN. **İki kapı da TÜM liste üzerinde çağırır** |
| `…::assertScopeDeclared` | Bildirilmemiş scope → `exit 1`. "Burada muafiyet yok" ile "bu yüzey hiç bildirilmedi" ayrımı |
| `…::MAX_EXCEPTION_DAYS` | Tavan **tek yerde** — kapılar yeniden bildiremez (contract test pinliyor) |
| `scripts/npm-audit-gate.mjs::scopeFor` | `<dir>` → `npm:<dir>`. Yeni bir workspace gate'lerken scope'u allowlist'e ekle |
| `backend/tests/contract/test_security_freeze_discipline_contract.py` | 7 test: imza zorunluluğu · `FROZEN_ADVISORIES` geri gelemez · iki kapı da ortak modülü okur · tavan tek yerde · workflow ↔ scope paritesi (npm **ve** container) |
| `docs/implementation/a11y_screen_reader_audit_runbook.md` | Denetçinin tek sayfası. `A11Y_HOST=<LAN IP>`, Admin, 23 rota + 10 akış, `SR-BULGU-nn`, "yapma" listesi |
| `docs/audit/…_results.md` §6 ▸ *How these counts were obtained* | Beş koşuluk kararlılık tablosu + **ilk-koşu-soğuk** kuralı |

## 3. Pazarlıksız — bir sonraki oturum bunları bozmasın

1. **`FROZEN_ADVISORIES` diye bir şey YOK.** Bir npm advisory'yi dondurman gerekirse
   `.github/security-allowlist.json`'a `scope: npm:<dir>` + `owner` + `expires` ile
   yaz. Kapıya hardcoded liste geri koyarsan contract test kırmızıya döner.
2. **`entries` boş ve boş kalması hedef.** Var olmayan bir açığa kayıt yazma — kapı
   `WARN — allowlisted but not reported` der ve istisna gerekçesiz kalır.
3. **Bir freeze'i yenilerken tarihi tek başına ötelemeyin** — gerekçeyi yeniden türet.
   Bu repoda yazılmış **üç** freeze'in **üçü de** gerekçesi çürüdüğü için öldü.
4. **A-08 için hiçbir belgeye `Complete`/`PASS`/`Done` yazma.** Defterin §1/§2/§3'üne
   otomatik çıktı **kopyalanmaz** (kontrat testi *"An empty template is not evidence"*
   cümlesini pinliyor).
5. **#514'e dokunma** — `human-only`; agent ne açar ne kapatır.
6. **Precheck sayısını tek koşuyla tazeleme.** İlk koşu soğuktur ve **eksik raporlar**;
   en az iki kez koş, sonrakini al. K-2/K-3/K-4/K-6 kararlı, **K-5 ve K-7 değil**.
7. **K-2..K-7'yi düzeltme** — her biri ayrı ürün kararı, RC §6.5'te bilerek gate dışı.
8. **Precheck probunun örnekleme zamanını değiştirme** — K-5 ve K-7'nin *anlamını*
   sessizce değiştirir. Yapılacaksa **bilerek** yapılır ve tablo aynı commit'te
   yeniden taban alınır.

## 4. Açık bırakılanlar (bu slice bilerek dokunmadı)

* **A-08 denetiminin kendisi** — randevu + insan saati, repo dışı.
* **#514'ün durumu** — insan kararı; (A) yeniden aç ya da (B) D-10 biçiminde imzalı sapma.
* **Precheck prob yarışı** — ölçüldü, adlandırıldı, düzeltilmedi (§2'deki 8. madde).
* **K-2..K-7** · **blocker 2** · **P11-1** (branch protection, repo ayarı) ·
  **P8-B2'nin PO yarısı** · **P8-B3b** · **P10-B2'nin PO yarısı** · **P4-3** (60 `modify_default`).
* **Container kapısının tetikleyicisi** — `security.yml` (main'e push, PR, haftalık cron).
  Bir istisnanın *süresi* artık her PR'da (npm kapısı) yakalanıyor, ama bir *container
  bulgusu* hâlâ yalnız o tetikleyicilerde yeniden taranıyor.

## 5. Çalışma yöntemi (işe yarayan)

* **Öncülü önce doğrula, sonra uygula.** Bu slice'ın asıl kazancı, talimatı harfiyen
  uygulamamak değil, talimatın kendi *"YENİDEN DOĞRULA"* maddesini uygulamak oldu.
  İmza hazırdı; öncül çürüktü; kayıt yazılmadı.
* **İki bağımsız kaynak.** `gh api /advisories/…` **ve** `npm audit --json`. Biri
  yanılsa öteki yakalardı.
* **Negatif kanıt, pozitiften önemli.** Bir kapının yeşil olması bir şey ölçtüğünü
  göstermez; **kırmızıya dönmesi gerektiğinde döndüğünü** göster.
* **Bir sayıyı yazmadan önce iki kez ölç.** Tek koşu bu slice'ta yanlış bir sayı
  yazdıracaktı.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 45

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — ADIM 44 merge olmuş OLMALI; olmadıysa DUR.
      `git fetch && git log --oneline origin/main -6 && gh pr list --state all`)

OTURUM BAŞLANGICI
  CLAUDE.md §Session START protocol · docs/ADIM44_LANDED_KICKOFF.md (bu dosya) ·
  docs/STAGE2_HANDOFF.md §Next · docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md
  §6 + §8 · docs/generated/repository_facts.md (SAYISAL OTORİTE).

DURUM
  RC blocker 4 → 2. Kalanlar: (1) A-08 insan denetimi — AÇIK, çıkış kriterleri 0/4;
  (2) kabul akışları CI kapısı değil. Verdict BLOCKED.
  ADIM 44: blocker 4 (react-router freeze) KAPANDI — imzayla değil KALDIRMAYLA
  (advisory upstream'de yeniden kapsamlandı, kurulu ağaç zaten yamalıydı);
  FROZEN_ADVISORIES silindi, imzasız npm freeze yazılabilecek yer kalmadı.

PAZARLIKSIZ
  · FROZEN_ADVISORIES geri gelmez; npm freeze'i allowlist'e owner+expires ile yaz.
  · Var olmayan bir açığa allowlist kaydı yazma.
  · A-08: hiçbir belgeye Complete/PASS/Done yazma; defterin §1/§2/§3'üne otomatik
    çıktı kopyalama; #514'e dokunma (human-only).
  · Precheck sayısını tek koşuyla tazeleme — ilk koşu soğuktur ve eksik raporlar.
  · K-2..K-7'yi düzeltme; precheck probunun örnekleme zamanını değiştirme.
  · Yeşile zorlama YOK. Blocker'ı "kapandı" yazmadan önce ölç.

SIRADAKİ İŞ — biri seçilir (PO kararı):
  (a) PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.
      ADIM 35 §4.1'in (c) engelini kapattı; kalan (a) faz-bölünmüş bar ve (b)
      book-etmeyen değerlendirme girişi `run_engine`'in gövdesine dokunur →
      **ADR §16 insan kapısı + ADR amendment'ı** gerekir, o kapıdan geçmeden başlama.
      Pointer: docs/ADIM35_LANDED_KICKOFF.md, docs/ADIM16_STEPPER_LANDED_KICKOFF.md §4.1
  (b) Blocker 2 — `flows`'u bir CI kapısına bağla (maliyet kararı: CI'da 12 konteynerlik
      ikinci yığın) + RC §6.2'deki iki SKIP'i kapat.
  (c) RC §6.7 artıkları — P8-B3b · P8-B2'nin PO yarısı · P10-B2'nin PO yarısı ·
      P11-6b · P4-3 (60 modify_default).

KAPANIŞ
  CLAUDE.md §Session CLOSING ritüelinin 6 maddesi ·
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check ·
  git diff origin/main -- docs/ | grep '^-## '   → BOŞ olmalı
```
