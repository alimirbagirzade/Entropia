# Stage K-03 kapanış + sonraki slice kickoff

> Bu doküman K-03 (engine funding sırası) kapandıktan **sonraki** oturumun devam tohumudur.
> Otorite sırası: bu doküman → `docs/STAGE2_HANDOFF.md` §Next → `docs/STAGE_BUILD_PLAN.md` →
> `docs/spec/NN_*`. Slice ayrıntısı gerekiyorsa `docs/PROJECT_HISTORY.md`'den **hedefli** oku.

## Neredeyiz

V1 ROADMAP COMPLETE + post-V1 + V18-R2/R3 + auth remediation. Üstüne **K-serisi kusur backlog'u**
kapandı: K-01 (#386) · K-02 (#393) · **K-03 (#398)** · K-04 (#397) · K-05 (#387) · K-06 (#395) ·
K-07 (#388).

- **alembic head:** `0035_portfolio_rules` (K-serisinde migration YOK).
- **`ENGINE_VERSION`:** `backtest-engine-v18-funding-step-order` (K-03). Öncesi: K-04
  `-full-pinning`, K-02 `-available-time-gate`, F-05 `-capability-matrix`.

## K-03 ne bıraktı (reuse anchor'ları — birebir sembol adları)

| Anchor | Nerede | Ne işe yarar |
|---|---|---|
| Kanonik 8 adımlık sıra | `domain/backtest/engine.py` modül docstring'i | doc 15 §9.3'ün motordaki **tek** yazılı beyanı; yeni bir bar-adımı eklerken buraya ve `# (n)` işaretine yaz |
| `# (2) K-03 / F-11 funding cost` | `engine.py`, bar döngüsünün başı | fee/carry'nin bağlanacağı yer — perp funding dışı maliyetler buraya takılır |
| `is_eligible_for_decision` | `domain/research_data/time_policy.py` | adım 1'in kanonik available-time kapısı (K-02); **her** research feed'i buradan geçir |
| `_position_size` / `_sleeve_capital` | `engine.py` | equity'ye bağlı iki choke-point; equity'yi değiştiren her yeni adım bunlardan ÖNCE çalışmalı |
| `ENGINE_VERSION` yorum zinciri | `domain/backtest/manifest.py` | her bump kendi bloğunu **ekler**, değer sonuncusu olur (K-04+K-03 çakışması böyle çözüldü) |
| `tests/unit/test_backtest_funding_step_order.py` | — | sıra iddialarının şablonu: aynı-bar olay sırası + before/after boyut assert'i |

**Yöntem notu (bu slice'ta işe yaradı):** bir sıra/ordering hatasını kanıtlamanın en ucuz yolu,
düzeltmeyi yazdıktan sonra `git stash push <dosya>` ile eski hâle dönüp yeni testleri koşmaktır —
5/6 kırıldı, yani testler boş değil. Kapanışta bunu PR açıklamasına yaz.

## Sırada ne var

1. **Blokaj — R2 product-owner imzası.** `docs/implementation/v18_final_acceptance.md` §4
   (D-1…D-9). İmza olmadan `entropia_v18_remediation_status.md`'deki R2 RE-OPENING banner'ı
   kalkmaz, hiçbir satır Complete olmaz (GAP madde 17).
2. **F-07 raw-id presentation sweep kalıntısı** — traceability tablosunda `Not started`;
   P-11/12/16 landed olduğu için gerçekten kalıntı var mı **empirik doğrulanmalı**.
3. **Açık dürüst sınırlar:** ekran okuyucu (NVDA/VoiceOver) denetimi yok; 10 sayfanın derin görsel
   kıyası eksik; A11Y-01 kontrast + A11Y-02 kayıtlı sapma.

## Çalışma döngüsü

1. `git fetch` → `git log --oneline origin/main -6` → `gh pr list --state all` (handoff STALE-BY-DEFAULT).
2. Dokunacağın alanın `docs/CODEMAPS/` haritasını oku, sonra `codebase-memory-mcp` ile sembolleri bul.
3. Dal: `feat/<slug>`. Direct-author (Workflow yok). Yeni dosyalar Bash heredoc ile (gate-free).
4. Yerel doğrulama:
   `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q`
   **`TEST_DATABASE_URL` ile worktree'ye özel izole DB kullan** — paylaşılan `entropia_test`
   üzerinde paralel worktree oturumları birbirinin şemasını siler ve dalgalı, ilgisiz hatalar üretir.
   Migration eklediysen ayrıca alembic up/down/up + yeni her `create_*` için L1 FK proof'u.
5. PR → `main`, `gh pr checks <n> --watch`. **Self-merge kapalı → merge için kullanıcıya sor.**
   Main ilerlediyse `git rebase origin/main` (ENGINE_VERSION çakışması beklenen bir durumdur).

---

## Paste-ready resume prompt

```
Entropia — devam. Session START protokolü: git fetch + `git log --oneline origin/main -6` +
`gh pr list --state all` ile NE'nin gerçekten merge olduğunu doğrula (handoff STALE-BY-DEFAULT).
Oku: docs/STAGE_K03_KICKOFF.md → docs/STAGE2_HANDOFF.md §Next → docs/STAGE_BUILD_PLAN.md.

Durum: K-serisi kusur backlog'u kapandı (K-01…K-07, PR #386/#387/#388/#393/#395/#397/#398).
alembic head 0035_portfolio_rules (migration yok), ENGINE_VERSION
backtest-engine-v18-funding-step-order (K-03: funding artık doc 15 §9.3 adım 2 — bar başında).

Sıradaki iş, öncelik sırasıyla:
1) F-07 raw-id presentation sweep kalıntısının EMPİRİK doğrulaması (traceability'de Not started,
   ama P-11/12/16 landed — gerçekten kalıntı var mı?).
2) R2 product-owner imzası bekleyen kalemler: docs/implementation/v18_final_acceptance.md §4
   (D-1…D-9). İmza gelmeden banner kaldırma / Complete işaretleme YOK.

Konvansiyonlar: direct-author (Workflow yok), yeni dosyalar Bash heredoc, ENGINE_VERSION bump'ı
davranış değişince ZORUNLU (yorum bloğu ekle, değeri değiştir). Backend verify:
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q
— TEST_DATABASE_URL ile worktree'ye özel izole DB kullan (paylaşılan entropia_test'te paralel
worktree'ler birbirini ezer). Ayrı dal, ayrı PR, NO AI attribution, self-merge yok.
```
