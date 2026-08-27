<!-- doc-status: current -->

# ADIM 121 landed — `G10`'un ön koşul tablosu tazelendi (DOCS-ONLY)

- **PR:** **#856** (dal `docs/stage-120-landed`)
- **Taban:** `origin/main` @ `f0be03f1` (`chore(deps): consolidate the four backend
  dependency bumps into one lock (#853)`); worktree ff edildi (0 ahead / 0 behind).
- **Diff:** tek karar belgesi + defter. `backend/src` ve `frontend/src`'te **sıfır satır**.
- **Bayrak:** `SHARED_ALLOCATION_STATUS` = `future_dev` — **el değmedi**.
  `ENGINE_VERSION` değişmedi, OpenAPI değişmedi, migration yok.

---

## Nerede duruyoruz

`G10` (ADR §16 **Gate 2**) **talep edildi ve İMZALANDI: `B — ERTELE`**
(`docs/decisions/closure_g10_containment_lift_gate2_2026-08-26.md`, ürün sahibi,
2026-08-26). **Red değildir.** Bu slice o belgenin **ölçüm** bölümlerini taze tabana
çekti ve **§Karar bloğuna dokunmadı**.

**Ön koşul sayımı, `f0be03f1`: 18 yeşil / 4 kırmızı.**

| # | Kırmızı | Sınıf |
|---|---|---|
| 17 | OD-2 mark policy + `MARK_STALENESS_POLICY` flip | mühendislik (`C9` öncesi) |
| 18 | `CONTENTION_SELECTION_STATUS` flip | mühendislik (`C9` öncesi) |
| 20 | `#544` / `G14`'ün `B` yarısı | **ürün kararı + migration** |
| 22 | A15 bump + A16 + A19 + A22 | `C9`'un kendi teslimatı |

---

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

- `docs/decisions/closure_g10_containment_lift_gate2_2026-08-26.md`
  - **§Ölçüm 3** artık bir **zincirdir**: `bda4aba8` 12/10 → `ae18f46b` 13/9 →
    `6759a495` 16/6 → **`f0be03f1` 18/4**. Eski ölçümler **silinmez**, tarihiyle kalır.
  - **§Yeniden talep koşulu** md. 3 kapandı; **md. 2 tek açık maddedir**.
  - **§Karar** bloğu **DOKUNULMAZ** — imzalı.
- `allocation/shared_mode_admission.py::non_executing_sleeve_holders` /
  `::mixed_record_time_bases` — ön koşul 15/16'nın sevk edilmiş hâli; çağrı yeri
  `commands/backtest_run.py` admission'ı, zarf O-02.

---

## Sıradaki kalem — ÖLÇÜLDÜ

**`G10` bugün yeniden talep EDİLEMEZ**: yeniden talep koşulu md. 2 (`G14`'ün `B` yarısı
sevk edilmiş + `#544` kapalı) sağlanmıyor.

Sıra: **`G14` Karar 2/3 imzası** → `B` (NET enum'unun kaldırılması, **bir migration**) →
`#544` kapanışı → **`C6`'nın P2/P8 yarısı** (`G11`+`G12` imzalı, tek slice'ta birlikte) →
17/18 (OD-2 mark policy + iki etiket flip) → **`G10` yeniden talep** → `C9`.

**`G15` ARTIK İMZALIDIR** — #855 (**ADIM 120**) `Seçenek B`'yi imzaladı ve **aynı
slice'ta uyguladı**; Ready Check leg 3 artık **FLAT**. Bu belgenin ilk yazımı onu
*imzasız* sayıyordu — o ölçüm doğruydu, **bayatladı**. `G15` bir `C9` ön koşulu
**değildir** (plan §2: *"nothing in this plan"*) → **18/4 sayısı etkilenmez.**

---

## Yapılmayanlar (bilerek)

- Üç tarihsel denetim belgesi (`closure_w0_…`, `final_closure_delta_audit_…`,
  `closure_c9_…verdict…`) **güncellenmedi** — `doc-status: historical`, ölçtükleri anı
  dondururlar (ADIM 65). `G8` md. 5 tazelemelerini istiyor; **gerilim çözülmedi.**
- `#559`'un kapanış yorumu **yazılmadı** (G8 md. 4) — **insan eylemi.**
- `#544` / `#559`'a dokunulmadı. Codemap tazelenmedi (yeni endpoint/tablo/sayfa/job yok).
- Suite koşulmadı → **hiçbir geçen/coverage sayısı iddia edilmiyor**, otorite CI.

---

## Paste-ready resume prompt

```
ENTROPIA — G14 Karar 2/3 imza hazırlığı + `B` yarısının ölçümü (C9 kritik yolu)

ÖNCE DOĞRULA: git fetch && git log --oneline origin/main -6 && gh pr list --state open
  Handoff BAYAT VARSAY. `docs/decisions/closure_g10_containment_lift_gate2_2026-08-26.md`
  §Ölçüm 3'ün SON tabanına bak ve 22 ön koşulu KODA KARŞI yeniden ölç — sayı taşıma.

BAĞLAM (ölçüldü, ADIM 121): `G10` (Gate 2) İMZALI = `B — ERTELE`, red değil. Yeniden
  talep koşulunun md. 1 ve 3'ü SAĞLANDI; **md. 2 tek açık maddedir** ve `C9`'u tutan
  tek kalem odur: `G14`'ün `B` yarısı (`NET` enum'unun KALDIRILMASI — bir MIGRATION) +
  `#544`'ün kapanması. Karar 1 imzalı (`C` şimdi + `B` `C9` öncesi), `C` #850 ile sevk
  edildi; **Karar 2 ve Karar 3'ün kutuları BOŞ.**

GÖREV (ikisi de KARAR DEĞİL — yazarın rolü hazırlık):
  1. ÖLÇÜM: `allocation/enums.py` + `rules.py` içinde `NET`'in sevk edilmiş yüzeylerini
     ve ÜRETİMDEKİ `'NET'` satırlarını say (Karar 2 tam olarak bunu soruyor). Sayı
     alınmadan Karar 2 imzalanamaz — `G15` emsali.
  2. `closure_g14_net_conflict_policy_2026-08-25.md` §Karar 2/3'ün ÖLÇÜM bölümlerini
     tazele; İMZA KUTULARINA DOKUNMA (☐ boş kalır, §Karar 1'in ☑'sine de dokunma).

YASAKLAR: `SHARED_ALLOCATION_STATUS`'a DOKUNMA (`future_dev` kalır). `ENGINE_VERSION`,
  golden digest'ler, containment gate'leri el değmez. Migration YAZMA — Karar 2 imzasız.
  `#544`/`#559` issue'larına dokunma (human-only). ADR-0002'ye amendment yazma.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; exit code'u AYRI oku;
  GateGuard'da 4 olguyu sun; kapanış ritüeli ZORUNLU.
```
