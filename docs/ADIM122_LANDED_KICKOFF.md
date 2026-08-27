<!-- doc-status: current -->

# ADIM 122 landed — `G14` Karar 2'nin ölçümü (DOCS-ONLY)

- **Taban:** `origin/main` @ `9bb14570` (`docs(stage-121): G10'un ön koşul tablosunu tazele (#856)`)
- **Diff:** tek karar belgesi (`closure_g14_net_conflict_policy_2026-08-25.md` §Ölçüm 5) + defter.
  `backend/src` / `frontend/src`'te **sıfır satır**.
- **Bayrak:** `SHARED_ALLOCATION_STATUS` = `future_dev` — **el değmedi**. `ENGINE_VERSION`
  değişmedi, OpenAPI değişmedi, migration yok.
- **İmza kutusu:** §Karar 2 **BOŞ** ve öyle bırakıldı (negatif kontrol: diff'te imza satırı **0**).

---

## Bu slice ne ölçtü

`G14` Karar 2 *"`'NET'` taşıyan **mevcut** satırlar ne olacak"* diye soruyor ve sessizce
kümenin **kapalı** olduğunu varsayıyor. **Ölçüldü — değil:**

| Ne | Ölçüm | Kanıt |
|---|---|---|
| NET kaydı bloklar mı | **HAYIR** | `rules.py` NET için `Sev.WARNING` (komşuları `Sev.BLOCKER`) |
| Kapı neyi sayar | yalnız BLOCKER | `rules.py::has_blockers`, üç çağıran `commands/allocation_plan.py` |
| Plan geçerli mi | **EVET** | `allocation_plan.py` → `valid = not has_blockers(issues)` |
| Kullanıcı seçebilir mi | **EVET** | `lib/allocation.ts::CONFLICT_POLICIES` üç üyeli, `NET` canlı |

→ **`'NET'` satırları bugün oluşmaya devam ediyor.** Karar 2 boş küme umuduna yaslanamaz;
`B3` (migration dursun) koşan bir sisteme karşı ayrıca kırılgan.

**`G15` emsali TERSİNE işliyor:** orada sayı **alınabilirdi**; burada sayı **alınsa bile
bayatlar** → bir ön koşul değil, **anlık görüntü**. Bu yüzden Karar 2 sayı olmadan da
imzalanabilir; sayı işin **büyüklüğünü** söyler, **cinsini** değil.

---

## Bu slice'ın bıraktığı çapalar

- `closure_g14_net_conflict_policy_2026-08-25.md` **§Ölçüm 5** — yukarıdaki tablo + sorgu
  + **B0** (dördüncü seçenek: **önce yazma yolunu dondur**, `Sev.WARNING` → `Sev.BLOCKER`
  ve `CONFLICT_POLICIES`'ten `NET`'i düşür). **B0 bir öneri DEĞİL**, ölçümün doğurduğu
  seçenektir ve **ayrıca imzalanmalıdır** — kendi başına bir davranış değişikliğidir.
- `rules.py::has_blockers` — allocation kaydının **tek** kapısı; yeni bir severity eklerken
  buradan geçir.

---

## Sıradaki kalem

**`G14` Karar 2 imzası** (B0 / B1 / B2 / B3) → `B` yarısı (NET enum'unun kaldırılması,
**bir migration**) → `#544` kapanışı → **`C6`'nın P2/P8 yarısı** → ön koşul **17/18**
(OD-2 mark policy + iki etiket flip) → **`G10` yeniden talep** → `C9`.

`G10` (Gate 2) **İMZALI = `B — ERTELE`**; yeniden talep koşulunun **md. 2** tek açık
maddesidir ve o da tam olarak yukarıdaki `G14` zinciridir.

---

## Yapılmayanlar (bilerek)

- **Üretim DB sayımı ALINMADI** ve **ikame edilmedi** (repo fixture'ı vekil değildir, `G15`
  kuralı). Sorgu belgede.
- **Hiçbir kutu doldurulmadı.** §Karar 2 boş; `B0` karara bağlanmadı.
- `#559`'un kapanış yorumu **yazılmadı** (`G8` md. 4) — **insan eylemi.**
- Ürün kodunda sıfır satır → **suite koşulmadı**, geçen/coverage **CI'ın otoritesinde**.

---

## Paste-ready resume prompt

```
ENTROPIA — G14 Karar 2 imzalandıktan SONRA: B yarısının migration'ı

ÖNCE DOĞRULA: git fetch && git log --oneline origin/main -6 && gh pr list --state open
  Handoff BAYAT VARSAY. closure_g14_net_conflict_policy_2026-08-25.md §Karar 2'nin imza
  kutusuna BAK — BOŞSA DUR, migration yazma (ADIM 119'un "varsayılan seçme" kuralı).

BAĞLAM (ADIM 122'de ölçüldü): NET bir WARNING'dir, BLOCKER değil -> 'NET' satırları
  bugün OLUŞMAYA DEVAM EDİYOR (rules.py::has_blockers yalnız BLOCKER sayar; plan
  valid=True alır; lib/allocation.ts::CONFLICT_POLICIES'te NET canlı). Küme DONMUŞ
  DEĞİL. §Ölçüm 5 bir DÖRDÜNCÜ seçenek kaydeder (B0 = önce yazma yolunu dondur) ve onu
  KARARA BAĞLAMAZ.

GÖREV (imza VARSA): imzalanan şıkkı uygula.
  - B0 ise: Sev.WARNING -> Sev.BLOCKER + CONFLICT_POLICIES'ten NET'i düşür (davranış
    değişikliği: frontend testleri ve rules testleri kırmızıya döner, YENİ markup'a
    hizala, OCC/Idempotency assertion'larına dokunma).
  - B1/B2/B3 ise: alembic revision + CHECK yeniden yazımı; mevcut satırların
    dispozisyonu imzalanan şıkka göre. L1 FK insert-order proof + up/down/up ZORUNLU.

YASAKLAR: SHARED_ALLOCATION_STATUS'a DOKUNMA. ENGINE_VERSION/golden digest'ler el değmez
  (bu değişiklik finansal sonucu oynatmamalı — oynatıyorsa DUR ve raporla).
  #544/#559'a dokunma (human-only). ADR-0002'ye amendment yazma.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; exit code'u AYRI oku;
  GateGuard'da 4 olguyu sun; kapanış ritüeli ZORUNLU.
```
