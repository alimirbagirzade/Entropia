<!-- doc-status: historical -->
# ADIM 155 landed — #854 set-once sevk edildi; test kasıtlı ters çevrildi, bedel pinlendi

## Nerede duruyoruz

Taban `origin/main` @ `5a0054e1` (ADIM 154). **ÜRÜN KODU DEĞİŞTİ (iki dosyada birer satır):**
iki dış-import pin yazıcısı set-once oldu (imza: Karar 1 = (b), ADIM 154). Migration yok ·
`ENGINE_VERSION`/OpenAPI/golden/ratchet el değmedi · **A-08 (#514) AÇIK, blocker DEĞİŞMEDİ
(1) → BLOCKED.** **Closes #854.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Çapa | Ne yapar |
|---|---|
| `link_batch_to_revision` / `link_normalized_to_revision` docstring'leri | Set-once kuralı + imzalı bedelin tek kaynak açıklaması |
| `test_external_import_pin_stability.py` (ters çevrilmiş) | Yeni dünyanın pini: pin kalır · READY kalır · stranded-N+1 bedeli gerçek olarak asserted |
| §ADIM 155 TUZAK notu | Commit'lenmemiş fix varken NC restore'u git'ten DEĞİL, ters-yama + sha256 ile |

## Sıradaki iş (imzalı kuyruk)

1. **#546+#536 matrix slice'ı:** `restrictions_filters.filters.action` capability matrix'e
   (ADIM 139 muhafız eksenleri hazır; TS aynası `backend/tools/export_capability_matrix.py`)
   + #536 Gap C allow-list muhafızı. Davranış DEĞİŞMEZ. Closes #546 + #536.
2. **#547 feature slice'ı:** Increasing Timeframe by Layer — issue'nun "Required work" listesi
   madde madde; exhaustion = custom_sequence emsali; `ENGINE_VERSION` PR'da açıkça. Closes #547.
3. **Tavan takibi:** post-fix korpus 3/3 kusursuz; 4. kusursuz koşu (bu PR'ın merge koşusu
   olabilir!) inince sıkıştırma slice'ı — tavanlar o PR'ın KENDİ CI artefaktından.

---

## Paste-ready resume prompt

```
Entropia — ADIM 156. Session START protokolünü uygula: git fetch, git log --oneline
origin/main -6, gh pr list --state all (handoff STALE-BY-DEFAULT). Sonra oku:
docs/ADIM155_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md (son "## Next") →
docs/PROJECT_HISTORY.md §ADIM 155 (hedefli).

DURUM: #854 kapandı (set-once sevk edildi). İmzalı kuyrukta iki iş:
  (1) #546+#536 matrix slice'ı — restrictions_filters.filters.action capability matrix'e +
      #536 Gap C allow-list muhafızı. Davranış değişmez, TS aynası yeniden üretilir.
      Closes #546 + #536. Buradan başla.
  (2) #547 — Increasing Timeframe by Layer (exhaustion = custom_sequence emsali;
      ENGINE_VERSION PR'da açıkça değerlendirilir). Closes #547.
Tavan takibi: post-fix korpus 3/3 kusursuz; 4. kusursuz main koşusu inince sıkıştırma
slice'ı (tavanlar o PR'ın KENDİ CI artefaktından; yerelden ASLA). #514 A-08 TEK BLOCKER.

KURALLAR: ölçmediğini iddia etme; öncülü defterin KENDİSİNDE doğrula; yeşil exit code kanıt
değildir; alt küme pytest'te --no-cov; çıplak worktree'de önce uv sync --all-extras;
NC restore'u commit'lenmemiş fix varken git'ten değil ters-yama+sha256 ile; kapanış ritüeli
ZORUNLU; kickoff'lardan yalnız EN YÜKSEK numaralı current; self-merge bloklu.
```
