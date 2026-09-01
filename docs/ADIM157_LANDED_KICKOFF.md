<!-- doc-status: current -->
# ADIM 157 landed — #547 sevk edildi: Increasing Timeframe by Layer

## Nerede duruyoruz

Taban `origin/main` @ `1d7c7e7e` (ADIM 156). **ÜRÜN KODU: 6 dosya** (`scaling.py` resolver+depth ·
`engine.py` kelepçe+3 çağrı · `config.py` description · `validators.py` remediation ·
`capabilities.py` satır flip · `manifest.py` bump). **`ENGINE_VERSION` DEĞİŞTİ**
(`backtest-engine-v18-increasing-tf-ladder`; golden'da yalnız `contract.execution_key` oynadı,
altı tripwire kasıtlı taşındı) · migration YOK · OpenAPI değişmedi · ratchet el değmedi ·
**A-08 (#514) AÇIK, blocker DEĞİŞMEDİ (1) → BLOCKED.** **Closes #547 — imzalı kuyruk BOŞALDI.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Çapa | Ne yapar |
|---|---|
| `scaling.py::layer_timeframe(config, n, *, base_timeframe=None)` | Üç modun tek rung çözücüsü; increasing = `CANONICAL_TIMEFRAMES[index(base)+N]`, base RUN olgusu |
| `scaling.py::increasing_ladder_depth(base)` | Motor kelepçesinin kaynağı — `len(sequence)`'in increasing analoğu; None/off-ladder base → 0 |
| `test_..._timeframe_mode.py::test_increasing_by_layer_without_a_pinned_bar_timeframe_never_scales` | Timeframe'siz revizyon sınırının pini — readiness bu boşluğu GÖREMEZ, muhafız motor kelepçesi |
| NC-2'nin ölçümü | "Runs out" davranışını taşıyan şey resolver DEĞİL, motor kelepçesi — kelepçeye dokunan her değişiklik exhaustion testlerini kırmalı |

## Sıradaki iş

**İmzalı kod kuyruğu BOŞ.** Açık hatlar:
1. **A-08 (#514)** — TEK blocker, human-only (SR-1 hiç başlamadı; 2/184 hücre). Ajan ne
   kapatabilir ne ilerletebilir.
2. **Tavan takibi (koşullu):** post-fix Lighthouse korpusu 3/3 kusursuz; **4. kusursuz
   main koşusu inince** sıkıştırma slice'ı — tavanlar o PR'ın KENDİ CI artefaktından,
   yerelden ASLA.
3. Yeni ürün kararı/imza inerse: önce `docs/decisions/` kutusunu ölç (ADIM 90: issue
   durumu · yazılı karar · imza kutusu — ayrışırsa otorite imza kutusu).

---

## Paste-ready resume prompt

```
Entropia — ADIM 158. Session START protokolünü uygula: git fetch, git log --oneline
origin/main -6, gh pr list --state all (handoff STALE-BY-DEFAULT). Sonra oku:
docs/ADIM157_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md (son "## Next") →
docs/PROJECT_HISTORY.md §ADIM 157 (hedefli).

DURUM: #547 kapandı — İMZALI KOD KUYRUĞU BOŞ. Kalan hatlar:
  (1) A-08 (#514) TEK BLOCKER, human-only — ajan ilerletemez.
  (2) Tavan takibi KOŞULLU: 4. kusursuz Lighthouse main koşusu inince sıkıştırma slice'ı
      (tavanlar o PR'ın KENDİ CI artefaktından, yerelden ASLA).
  (3) Yeni imza/karar inmişse docs/decisions/ kutusunu ÖLÇ (ADIM 90 üç-ölçüm kuralı);
      açık issue listesini tara — imzasız karar kalemine kod yazma.
İş yoksa: durumu raporla ve dur; iş İCAT ETME.

KURALLAR: ölçmediğini iddia etme; öncülü defterin KENDİSİNDE doğrula; yeşil exit code
kanıt değildir (exit code'u AYRI oku); alt küme pytest'te --no-cov; vitest
--no-file-parallelism; NC restore'u ters-yama+sha256 (git checkout DEĞİL); suite koşarken
ağaca DOKUNMA (repository_facts dahil); ENGINE_VERSION bump'ında altı tripwire + golden +
facts AYNI commit'te; kapanış ritüeli ZORUNLU; kickoff'lardan yalnız EN YÜKSEK numaralı
current; self-merge bloklu.
```
