<!-- doc-status: historical -->

# ADIM 56 landed — A-08 denetimi BAŞLADI (SR-2 oturum 1), sıradaki oturum

> Kayıt: `docs/PROJECT_HISTORY.md` §ADIM 56. Bu belge **devam noktasıdır**, kayıt değil.

## Nerede duruyoruz

**A-08 denetimi artık "yapılmadı" değil, "başladı ve bitmedi".** Defter bir insanın
duyduğu **2 hücre** taşıyor (rota 1, A-1 + A-2). Buna rağmen:

| Kapı | Durum |
|---|---|
| Çıkış kriterleri | **0 / 4** — dördü de ☐ |
| Section A | **2 / 184** hücre (SR-2 yarısı), **0 / 23** rota TAM |
| Section B | **0 / 10** akış |
| SR-1 (NVDA/Firefox/Windows) | **hiç başlamadı** |
| Denetçi rolü | **atanmadı** — oturum 1'i ürün sahibi koştu (`neither`) |
| Blocker sayısı | **1 (yalnız A-08)** · verdict **BLOCKED** |
| GitHub #514 | **AÇIK** (2026-08-12T11:08:58Z) — kullanıcı açık kalmasına karar verdi |

**Hiçbir belge A-08'i `Complete`/`PASS`/`Done` gösteremez.** Kapı issue'nun durumu değil,
`docs/audit/a11y_screen_reader_audit_results.md` §5'in dört kriteridir.

## Sıradaki oturum tam olarak nereden devam eder

1. **Rota 1'in `A-3`'ü** — `h1 → h3` atlaması (K-5). Oturum 1'de soruldu, cevap
   *"atlamayı fark etmedim"* geldi ve **sayılmadı**: "gezindim, yanılmadım" ile "seviyelere
   bakmadım"ı ayırmıyor. **Sorulacak soru budur:** *VO rotorunda başlık listesini aç
   (`VO+U` → Headings); listede kaç seviye görüyorsun, `h2` var mı, `h1`'den sonra doğrudan
   `h3` mü geliyor?* Cevap seviyeleri **adlandırmalı**, yoksa hücre yine `—` kalır.
2. Sonra rota 1'in **A-4…A-8**'i, sonra **rota 2–23**, sonra **§2'nin on akışı**.
3. Ondan sonra **SR-1 kombinasyonunun tamamı** (Windows + NVDA + Firefox gerekir).

**Yığın:** `scripts/a11y-audit-stack.sh up` → `… validate` (güncel main'de 9/9).
Reçete: `docs/implementation/a11y_screen_reader_audit_checklist.md` ·
Runbook: `docs/implementation/a11y_screen_reader_audit_runbook.md`.

## REUSE — bu slice'ın bıraktığı çapalar

- `docs/audit/a11y_screen_reader_audit_results.md` — §0 SR-2 blok (doldurulmuş biçim
  örneği), §1 rota 1 satırı, §5 oturum günlüğü (**"nereden devam edilir" satırı burada**).
- `backend/tests/contract/test_a11y_audit_prep_contract.py` — **21 test**, defterin
  invariant'larını pinler. **Deftere dokunan her değişiklikten sonra koştur.**
- `docs/audit/…` §STATUS ▸ *Tracking-issue state* — #514 ayrışmasının **kanonik** kaydı;
  başka hiçbir belge bunu yeniden anlatmaz, hepsi buraya işaret eder.

## Pazarlıksız — bu slice'ta bedeli ödendi

- **Sayaç kanonik biçimde kalır.** `test_declared_completion_matches_the_cells` sayacı
  hücrelerden yeniden hesaplar; düzyazıya çevirmek kapıyı kırar. Açıklamayı **altına** yaz.
- **`-X theirs` invariant düşürebilir.** Bu slice'ta `"An empty template is not evidence"`
  sessizce kayboldu. Her strateji-çözümünden sonra **sözleşme testini koştur**.
- **Main'in gerisinde kalan dal merge EDİLEMEZ** — 22/22 yeşil olsa bile
  (`strict_required_status_checks_policy`, ruleset `20765617`). Çözüm main'i içeri almak;
  **ruleset bypass edilmez**.
- **Docs PR'ı merge etmeden önce** `git diff origin/main..HEAD -- docs/ CLAUDE.md | grep '^-#'`
  koştur — bu repoda bayat base'li docs PR'ı **üç kez** kayıt sildi.
- **`—` sessiz bir `PASS` değildir**, sayaçlar yukarı yuvarlanmaz, ve otomatik hiçbir çıktı
  (axe, Lighthouse, precheck) §1/§2/§3'e **kopyalanamaz**.

## Paste-ready resume prompt

```
Entropia — A-08 ekran okuyucu denetimi, SR-2 oturum 2.

Önce doğrula (handoff STALE-BY-DEFAULT): git fetch && git log --oneline origin/main -6.
Sonra oku: docs/ADIM56_LANDED_KICKOFF.md, docs/PROJECT_HISTORY.md §ADIM 56, ve
docs/audit/a11y_screen_reader_audit_results.md §STATUS + §1 + §5.

Durum: A-08 denetimi BAŞLADI ama BİTMEDİ. Defterde 184 Section A hücresinin 2'si dolu
(rota 1: A-1, A-2), 10 akışın 0'ı, SR-1 hiç başlamadı, çıkış kriterleri 0/4. GitHub #514
AÇIK ve öyle kalacak (kullanıcı kararı) — agent onu ne kapatabilir ne açabilir.

Bu oturumda yapılacak: SR-2'yi rota 1'in A-3'ünden devam ettir. A-3 oturum 1'de sorulmuştu
ama cevap sayılmadı ("atlamayı fark etmedim" — "gezindim, yanılmadım" ile "seviyelere
bakmadım"ı ayırmıyor). Denetçiye VO rotorunda başlık listesini açtır (VO+U → Headings) ve
gördüğü seviyeleri ADLANDIRMASINI iste; adlandırmazsa hücre `—` kalır. Sonra A-4…A-8,
sonra rota 2-23.

Rolün SCRIBE: hücreleri yalnız insanın duyduğundan yaz. axe/Lighthouse/precheck çıktısını
§1/§2/§3'e ASLA kopyalama. Koşulmayan hücre `—` kalır, sayaçları yukarı yuvarlama,
hiçbir belgeye A-08 için Complete/PASS/Done yazma.

Yığın: scripts/a11y-audit-stack.sh up && scripts/a11y-audit-stack.sh validate (9/9 bekle).
Deftere dokunduktan sonra: cd backend && uv run pytest tests/contract/test_a11y_audit_prep_contract.py -q --no-cov
ve uv run --project backend python scripts/generate_repository_facts.py --check (repo kökünden).

Merge etmeden önce: dal main'in gerisindeyse merge REDDEDİLİR (ruleset 20765617, strict) —
main'i içeri al, ruleset'i bypass etme; ve `git diff origin/main..HEAD -- docs/ CLAUDE.md
| grep '^-#'` ile kayıt silmediğini doğrula.
```
