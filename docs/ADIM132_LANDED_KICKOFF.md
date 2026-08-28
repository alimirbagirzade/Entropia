<!-- doc-status: historical -->

# ADIM 132 — `C9` / ADIM 20 İNDİ: CONTAINMENT KALKTI · sıradaki kalem **A-08 (insan)**

**Taban:** `origin/main` @ `305cccec` (ADIM 131, PR #868) · **Dal:** `feat/stage-132-c9-containment-lift`

---

## Nerede duruyoruz

**`SHARED_ALLOCATION_STATUS` = `active_v1`.** Paylaşımlı sermaye tahsisi bu build'de
**çalışır**. `ENGINE_VERSION` → `backtest-engine-v18-unified-clock-portfolio` (A15'in ikinci
bump'ı). 22 ön koşulun **22'si** kapalı. Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 132.

**AMA RC VERDICT'İ HÂLÂ `BLOCKED`.** `C9` blocker sayısını **değiştirmez**: tek blocker
**A-08** (ekran okuyucu denetimi, GH **#514**, `human-only`) ve o **AÇIK**. `C9`'un inmesi
"ürün hazır" demek **değildir**.

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

| Ne | Nerede |
|---|---|
| OD-2 sınırı + sayaç | `execution/portfolio_ledger.py::MARK_STALE_AFTER_MS` · `MarkPrice.is_stale_refused` · `PortfolioValuation.stale_refused_items` |
| Politika adı (İKİ yazım, parite testli) | `manifest.py::MARK_STALENESS_POLICY` + `execution/provenance.py::MARK_STALENESS_POLICY` = `carry_forward_bounded_v1` |
| OD-3 etiketi | `execution/arbitration.py::CONTENTION_SELECTION_STATUS` = `approved` |
| Dünya başına metin | `allocation/capability.py::SHARED_ALLOCATION_ACTIVE_MESSAGE` / `_REMEDIATION` / `_DEPENDENCY` |
| Contained dünya fixture'ı | `_contained(monkeypatch)` — dört test modülünde |

## Sıradaki kalem — **KOD DEĞİL, İNSAN İŞİ**

1. **A-08 ekran okuyucu denetimi.** Defter **2/184** hücre, **0/10** akış, SR-1 hiç
   başlamadı → dört çıkış kriteri de ☐. Ajan #514'ü **ne açar ne kapatır**.
2. **`G8` md. 4'ün kapanış yorumu** (#559) — hâlâ yazılmadı, insan eylemi.
3. **OD-2 mark yolunu üretime bağlamak** — ayrı bir slice ve **ürün kararı**; bugün
   `attribute()` üretimde çağrılmıyor (aşağıdaki dürüst sınıra bak).

## Dürüst sınırlar — devralan bunları iddia ETMESİN

- **OD-2 politikası sevk edildi ama ULAŞILABİLİR DEĞİL.** `attribute()`'ün `backend/src`'te
  sıfır çağıranı var; `MarkPrice` yalnız testlerde kuruluyor. Ön koşul 17'nin istediği
  *"policy built + label flipped"* karşılandı; *"marks üretimde akıyor"* **karşılanmadı ve
  iddia edilmiyor**.
- **`E(t)` realized-only.** Mark onu **hiç** etkilemez (`portfolio_ledger.py` modül
  docstring'i otoritedir; ADR §5'in prozası bu eksende gevşektir).
- **`stale_after` = 900 sn ÖDÜNÇ.** Kanon pozisyon-mark için sayı vermiyor. Sayıyı
  değiştirmek **yeni bir `carry_forward_bounded_vN` + `ENGINE_VERSION` bump** gerektirir.
- **Frontend'de sıfır satır** → frontend kapıları KOŞULMADI, otorite CI.
- **Dört denetim belgesi `doc-status: historical` ve el değmedi**;
  `unified_portfolio_oracle_acceptance.md`'nin A16/A17/A21 satırları **karşı-olgusaldır ve
  otorite değildir** (ADIM 130'da ölçüldü, bilerek düzeltilmedi).

## Tuzaklar

- **Bir imzanın "var" olması ile "BU AĞAÇTA var" olması ayrı iddialardır.** Bu slice
  `G10` imzasız bir ağaçta başladı (imza merge edilmemiş #868'deydi) ve **durdu**.
- **Wrapper subshell'in exit code'u pytest'in DEĞİLDİR** — `$?`'i pytest'ten hemen sonra,
  ayrı yaz. Ve **tamponlanmış çıktı bitmemiş koşu gibi görünür**: özet satırı yoksa dosyayı
  tekrar oku, "kesildi" sonucuna atlama.
- **Alt küme koşarken `--no-cov`.**
- **Uzun suite koşarken `docs/` düzenleme** — documentation-truth kapısı çalışma ağacını okur.
- **`ruff format` test dosyalarını yeniden biçimlendirir**; suite'i ondan SONRA koş.

## Paste-ready resume prompt

```
ENTROPIA — ADIM 132 SONRASI (C9 İNDİ, CONTAINMENT KALKTI)

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -6 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3

DURUM: SHARED_ALLOCATION_STATUS = active_v1 (ADIM 132 / C9). ENGINE_VERSION =
backtest-engine-v18-unified-clock-portfolio. 22/22 ön koşul kapalı. AMA RC verdict
HÂLÂ BLOCKED — tek blocker A-08 (#514, human-only, AÇIK) ve C9 onu değiştirmez.
Otorite: docs/PROJECT_HISTORY.md §ADIM 132 + docs/ADIM132_LANDED_KICKOFF.md.

SIRADAKİ İŞ KOD DEĞİL: A-08 denetimi (insan) · G8 md.4 kapanış yorumu (#559, insan).
Mühendislik istenirse: OD-2 mark yolunu üretime bağlamak — AYRI slice ve ÜRÜN KARARI;
bugün attribute() üretimde çağrılmıyor (dürüst sınır, kickoff §Dürüst sınırlar).

YASAKLAR: #514'e DOKUNMA (ne aç ne kapat). RC verdict'ini "BLOCKED değil" diye yazma.
  "OD-2 üretimde akıyor" DEME — sevk edildi ama ulaşılamaz.
  stale_after (900 sn) ödünçtür; değiştirmek yeni policy version + ENGINE_VERSION bump ister.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; her yeni assertion için
  AYIRT EDİCİ negatif kontrol; kapatmadığını `covered` İŞARETLEME; kapanış ritüeli ZORUNLU.
```
