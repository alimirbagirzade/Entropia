<!-- doc-status: historical -->
# ADIM 156 landed — #546+#536 tek slice'ta: action matrise, conflict literalleri muhafıza

## Nerede duruyoruz

Taban `origin/main` @ `3f6069e6` (ADIM 155). **ÜRÜN KODU: yalnız `capabilities.py`**
(6 matris satırı + `_read_filter_actions`); golden 50 digest bayt bayt aynı →
`ENGINE_VERSION` değişmedi · migration YOK · OpenAPI değişmedi · ratchet el değmedi ·
**A-08 (#514) AÇIK, blocker DEĞİŞMEDİ (1) → BLOCKED.** **Closes #546 + #536.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Çapa | Ne yapar |
|---|---|
| `_FREE_FORM_FIELDS` + `test_action_vocabulary_matches_the_engine` | Serbest-biçim (Literal'siz) matris alanı deseni: eksen-1 yerine alanın kendi sözlük pini, İKİ YÖNLÜ motor paritesi |
| `_UNGATED_CONFLICT_LITERALS` + guard testi | Yeni conflict literali ya matriste ya açık allow-list'te — tam eşitlik + disjointness |
| `CAPABILITY_CONFIG_ONLY_FIELDS` (FE) | Hiçbir formun render etmediği matris alanı için #539-tripwire muafiyet deseni (belgeli) |
| `_read_filter_actions` docstring'i | Okuyucu = motorun okuma SIRASI; üç skip kolu üç ayrı assertion'la pinli |

## Sıradaki iş (imzalı kuyruğun SON kalemi)

1. **#547 feature slice'ı:** Increasing Timeframe by Layer — issue'nun "Required work"
   listesi madde madde; exhaustion = custom_sequence emsali; `ENGINE_VERSION` PR'da
   açıkça değerlendirilir. Closes #547.
2. **Tavan takibi:** post-fix korpus 3/3 kusursuz; 4. kusursuz main koşusu inince
   sıkıştırma slice'ı — tavanlar o PR'ın KENDİ CI artefaktından, yerelden ASLA.

---

## Paste-ready resume prompt

```
Entropia — ADIM 157. Session START protokolünü uygula: git fetch, git log --oneline
origin/main -6, gh pr list --state all (handoff STALE-BY-DEFAULT). Sonra oku:
docs/ADIM156_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md (son "## Next") →
docs/PROJECT_HISTORY.md §ADIM 156 (hedefli).

DURUM: #854 + #546 + #536 kapandı. İmzalı kuyrukta TEK iş kaldı:
  (1) #547 — Increasing Timeframe by Layer. Issue'nun "Required work" listesi madde madde:
      layer_timeframe/layer_bucket yeniden kullanımı · exhaustion = custom_sequence emsali ·
      matrix satırı active_v1'e + TS aynası · bayat remediation cümlesi kalkar ·
      test_backtest_scaling_timeframe_mode.py aynası. ENGINE_VERSION sorusu PR'da AÇIKÇA
      değerlendirilir (golden oynarsa bump + yeniden üretim AYNI commit'te). Closes #547.
Tavan takibi: 4. kusursuz main koşusu inince sıkıştırma slice'ı (tavanlar o PR'ın KENDİ CI
artefaktından). #514 A-08 TEK BLOCKER, human-only.

KURALLAR: ölçmediğini iddia etme; öncülü defterin KENDİSİNDE doğrula; yeşil exit code kanıt
değildir (exit code'u AYRI oku); alt küme pytest'te --no-cov; vitest --no-file-parallelism;
NC restore'u commit'lenmemiş fix varken git'ten DEĞİL ters-yama+sha256 ile (ADIM 155'in
tuzağı ADIM 156'da BİR KEZ DAHA yaşandı); suite koşarken ağaca DOKUNMA (repository_facts
dahil — ADIM 156'da 1 test bu yüzden düştü, koşu atıldı); kapanış ritüeli ZORUNLU;
kickoff'lardan yalnız EN YÜKSEK numaralı current; self-merge bloklu.
```
