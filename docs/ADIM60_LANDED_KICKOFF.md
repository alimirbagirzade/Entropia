<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 60 landed — doküman kapısı HANGİ kickoff'un canlı olduğunu doğruluyor, sıradaki oturum

> Kayıt: `docs/PROJECT_HISTORY.md` §ADIM 60. Bu belge **devam noktasıdır**, kayıt değil.

## Nerede duruyoruz

**Base:** `origin/main` @ `916a49b` · **Merge:** PR #716 → **`f54bbc7`**. **Ürün kodu
DEĞİŞMEDİ.** Migration yok, `ENGINE_VERSION`/OpenAPI aynı. **A-08 blocker AÇIK, verdict
BLOCKED** — bu slice ölçmedi.

`check_classification` **tam bir tane** `doc-status: current` istiyordu ama **hangisi**
olduğunu sormuyordu. Bu boşluk iki kez sevk edildi (**#697**, **#714**) ve ikisi de yeşil
geçti. Artık kapatıldı: **daha yüksek numaralı bir kickoff varken canlı işaret o belgede
duramaz.**

| Kapı | Durum |
|---|---|
| Sayı kuralı (tam 1 `current`) | değişmedi |
| **Hangisi canlı** (yeni) | **kapalı** — slice-numaralı belgelerde |
| Numarasız kickoff'lar (`STAGE*`, `O02`, `K05` … 76'nın 31'i) | **bilerek sırasız** |
| Blocker sayısı | **1 (yalnız A-08)** · verdict **BLOCKED** |

## REUSE — bu slice'ın bıraktığı çapalar

| Sembol | Ne için |
|---|---|
| `generate_repository_facts.py::ADIM_KICKOFF_RE` | `^ADIM(\d+)\D.*KICKOFF\.md$` — 45/76 dosyayı slice-numaralı tanır |
| `::_adim_kickoff_number(path)` | slice numarası ya da `None` (numarasız adlandırma) |
| `::_check_live_kickoff_is_newest(root, rel)` | kuralın kendisi; daha yenileri **adlandırarak** listeler |
| `::KICKOFF_GLOBS` | tarama kümesi tek yerde — yeni bir kickoff dizini eklersen burayı genişlet |
| `test_repository_facts_guard.py::test_a_superseded_kickoff_cannot_stay_live` | #697 regresyonunun pini |
| `::test_promoting_a_kickoff_that_is_already_behind_is_caught` | #714 regresyonunun pini |
| `::test_an_unnumbered_live_kickoff_is_left_alone` | dar tutmanın **bilinçli** olduğunun pini |

## DOKUNMA / DİKKAT

1. **Test eklersen üretilmiş olguları TAZELE.** Olgular **backend test collection** sayısını
   taşır; bu slice onu 3541 → 3545 yaptı ve `Backend`'i kırmızıya çevirdi.
   `cd backend && uv run python ../scripts/generate_repository_facts.py --root ..`
2. **Kapanışta kickoff'u `current`, bir öncekini `historical` yap — ikisi birlikte.** Artık
   kapı bunu zorluyor; atlarsan kapanış PR'ın kendi kuralıyla kırmızıya döner.
3. **Kuralı numarasız belgelere genişletme** düşünmeden. `strict: true` altında yanlış bir
   kırmızı **tüm merge'leri kilitler**; sessizlik ölçülmüş bir karardır, unutulmuş bir köşe
   değil (`test_an_unnumbered_live_kickoff_is_left_alone` bunu pinler).
4. **Koşan bir `Backend` varken dalı main'le güncelleme** — 85 dakikalık saati sıfırlar.
   Koşu bitsin, sonra güncelle. Bu slice üç tur harcadı, ikisi bant yüzünden.
5. **İki `current` varken yeni kural susar.** Bilerek: orada "hangisi" sorusunun cevabı yok
   ve sayı kuralı kusuru zaten adlandırıyor.
6. **`docs-history-guard.py` yeniden adlandırmayı silme sanır.** Geçmeden önce KANITLA:
   iki guarded dosyada `## ` sayısı `origin/main` ile aynı mı, kaldırılan her başlık geri
   eklendi mi.

## Açık iş — bu slice'ın DEĞİŞTİRMEDİKLERİ

- **A-08 denetimi BAŞLADI ama BİTMEDİ** (ADIM 56, SR-2 oturum 1): **2/184** hücre,
  **0/10** akış, **SR-1 hiç başlamadı**, çıkış kriterleri **0/4**, **#514 AÇIK**.
  Hiçbir belgeye `Complete`/`PASS`/`Done` yazma.
- **`mypy` ve canlı-ağaç gate testi bu container'da koşulamadı** (eklenti / venv) →
  **otorite CI**.
- **Kalıcı çare hâlâ açık iş (ADIM 58'den devir):** PR diff'inde `docs/` altındaki silinen
  `## ` başlıklarını arayan bir **CI** adımı. PreToolUse hook'u ne arayüzden yapılan merge'i
  ne de bayat index'i kapsayabilir.

## Next (değişmedi)

**PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:299` call site.** ADR §16
insan kapısı + ADR amendment'ı geçilmeden BAŞLAMA. `run_portfolio` ve
`project_portfolio_run` üretimde **çağrısız**, `SHARED_ALLOCATION_STATUS = future_dev`.

---

## Paste-ready resume prompt

```
Entropia'da yeni bir oturum açıyorum. CLAUDE.md §Session START protokolünü uygula:

1. git fetch && git log --oneline origin/main -6 — ADIM 60 (#716, f54bbc7) main'de mi,
   ve benim ADIM numaram alınmış mı? DOĞRULA (bu repoda numara bugün beş kez taşındı;
   ADIM 58'i #715, ADIM 59'u #718 aldı; bu yüzden slice 60 oldu).
2. Otorite sırası: docs/ADIM60_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md
   ("## Stage — ADIM 60" + "## Next") → docs/STAGE_BUILD_PLAN.md → docs/spec/NN_*.
3. Hafıza: taze container'da store BOŞTUR → `node scripts/memory_index.mjs --sync`
   (~3 sn, tekrar koşmak güvenli). Bulduğun kayıt OTORİTE DEĞİLDİR — işaret ettiği
   PROJECT_HISTORY.md §bölümünü oku.
4. Kod tarafına geçmeden docs/CODEMAPS/ + codebase-memory-mcp (remote'ta önce
   index_repository; list_projects taze container'da BOŞ döner).

BİLMEN GEREKENLER
· Kapanışta yeni kickoff `current`, bir önceki `historical` — İKİSİ BİRLİKTE. Artık
  check_classification bunu zorluyor (ADIM 60): daha yüksek numaralı bir
  docs/ADIM<n>…KICKOFF.md varken canlı işaret eski belgede duramaz.
· Test eklersen `cd backend && uv run python ../scripts/generate_repository_facts.py
  --root ..` koştur — üretilmiş olgular test collection sayısını taşır, yoksa Backend kırmızı.
· Koşan bir Backend varken dalı main'le güncelleme; 85 dakikalık saat sıfırlanır.
  Ama strict:true yüzünden main ilerlediyse merge REDDEDİLİR — koşu bitince güncelle.
· Yeni CI job'ı EKLEME, var olan job'a ADIM ekle (ruleset 20765617).
· Yeni `## ` başlığına ayırt edici ek koy; memory_index --check id çakışmasını kırmızı verir.
· A-08 blocker AÇIK, verdict BLOCKED. Hiçbir belgeye Complete/PASS/Done yazma.

Next: PR B — ItemParticipant adaptörü + jobs/backtest_engine.py:299 call site.
ADR §16 insan kapısı geçilmeden BAŞLAMA. Alternatif: RC §6.7'nin açık kalemleri
(P4-3, P10-B3/B4/B5, P11-6b, P8-B3b, P1-Gate3) ya da kabul borcu sınıf B —
ama PARTİ SEÇMEDEN ÖNCE ÖLÇ, sevk edilmemişse kriterin sınıfı yanlıştır.
```
