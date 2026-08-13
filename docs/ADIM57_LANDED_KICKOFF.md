<!-- doc-status: historical -->

# ADIM 57 landed — plugin hook'ları kurulumdan bağımsız, sıradaki oturum

> Kayıt: `docs/PROJECT_HISTORY.md` §ADIM 57. Bu belge **devam noktasıdır**, kayıt değil.

## Nerede duruyoruz

**Ürün ekseninde hiçbir şey değişmedi.** `backend/src`, `alembic`, `frontend/src` el
değmedi; migration yok, `ENGINE_VERSION` aynı. **A-08 blocker AÇIK, blocker sayısı 1,
verdict BLOCKED.** Bu slice ajan araç zincirini onardı, ürünü değil.

Kapanan boşluk şuydu: `plugins/entropia-maintenance` **kurulmuyor** ve bu yüzden onun
içindeki iki **bloklayıcı** guard remote'ta hiç koşmuyordu — üstelik biri (`guard-git.sh`)
tam olarak üç kez yaşanmış bir regresyonu (#590 211 satır, #604 194 satır) durdurmak için
yazılmıştı ve hiçbir CI kapısı `docs/` okumuyor.

## Bu slice'ın bıraktıkları (reuse anchor'ları, tam sembol adlarıyla)

| Anchor | Ne |
|---|---|
| `.claude/settings.json` → `hooks.PreToolUse` | iki yeni kayıt; yollar `${CLAUDE_PROJECT_DIR:-.}/plugins/entropia-maintenance/hooks/…` |
| `scripts/hook-guard-proof.sh` | guard **davranış** kapısı — 19 beklenti (6 engelleme, 13 geçiş) + kaydın kendisini assert eder |
| `.github/workflows/ci.yml` → `frontend` job → adım **`Agent hook behaviour proof`** | kapının CI bağlantısı (**yeni job değil**) |
| `scripts/agent-config-gate.mjs` | değişmedi — yeni yolları zaten kapsıyor, negatifi bu slice'ta 3 mutasyonla kanıtlandı |
| `plugins/entropia-maintenance/README.md` §**Çift koşma** | *"kopya bırakılmadı"* kararının gözden geçirilmiş hâli + ölçülmüş bedel |
| `.claude/README.md` | `enabledPlugins` ≠ kurulum ölçümü; ADIM 53'ün fazla iddialı cümlesi düzeltildi |

## Sıradaki oturum için işaretler

**Ana eksen değişmedi: `## Next` hâlâ PR B** (`ItemParticipant` adaptörü +
`jobs/backtest_engine.py:298` call site) ve o **ADR §16 insan kapısının** arkasında.
Detay: `docs/ADIM35_LANDED_KICKOFF.md`.

**Bu slice'ın açık bıraktıkları — hiçbiri blocker değil:**

1. **Plugin hâlâ kurulu değil.** Ajanlar, skill'ler, slash command'lar ve öteki üç hook
   remote'ta yüklenmiyor. Kurmak **insan kararıdır** (yerel `/plugin install`). Bu slice
   sadece iki bloklayıcı guard'ı kurtardı — **"plugin artık çalışıyor" DEME.**
2. **`guard-git.sh` aşırı-engelliyor** (komut dizesinin tamamında desen arar). Bilinçli,
   fail-closed. Düzeltmek istersen: eşleşmeyi `git push` argüman listesine daraltmak
   gerekir ve **o daraltma bir kaçırma riski açar** — daraltmadan önce
   `scripts/hook-guard-proof.sh`'e o kaçırmayı yakalayan bir beklenti ekle.
3. **`Frontend` job'ının yeni adımı CI'da koşmadı** (yerel koştu). İlk yeşil koşuda
   job log'undan **gerçekten koştuğunu** doğrula — ADIM 34'ün "0-job'lı sahte yeşil"
   dersi burada da geçerli.

## Yöntem — bu slice'ta işe yarayan çalışma döngüsü

- **Ölç, sonra karar ver.** Bu slice'ın tamamı tek bir `cat installed_plugins.json`
  ölçümüne dayanıyor. "Yapılandırma bozuk" teşhisi yanlış olurdu ve bir sonraki oturumu
  `settings.json`'ı onarmaya gönderirdi.
- **Pozitif yeşil kanıt değil.** Her kapı, geçirmesi gereken girdiyle de ateşlendi; kapının
  kendisi de üç mutasyonla kırmızıya çevrildi. Bir guard'ın *her şeyi* engellemesi
  pozitif-yalnız bir testi geçer.
- **Yeni CI job'ı EKLEME.** Ruleset `20765617` 16 required check adını **başlıkla** tanır;
  üretilmeyen bir ad tüm merge'leri kilitler (ADIM 49). Var olan job'a **adım** ekle.
- **Hook artık senin de kapındır.** `git push --force`, self-merge ya da bu desenleri
  *içeren* bir heredoc/döngü Bash çağrını bloklar. Metni Write ile **dosyaya** yaz, sonra
  dosyayı koştur.

---

## Paste-ready resume prompt

```
Entropia — ADIM 58

ÖNCE CLAUDE.md §Session START protokolünü uygula: git fetch, git log --oneline
origin/main -6, gh pr list --state all. ADIM numarasını `grep '^## ADIM'
docs/PROJECT_HISTORY.md | tail -3` ile DOĞRULA — bu depoda numara beş kez taşındı ve
merge edilmiş ad kazanır.

DURUM (ADIM 57 sonrası, doğrula):
- A-08 blocker AÇIK, blocker sayısı 1, verdict BLOCKED. #514 açık (human-only —
  agent ne kapatabilir ne açabilir). Hiçbir belgeye A-08 için Complete/PASS yazma.
- alembic head `0043_i08_registry_strategy_fks`, ENGINE_VERSION değişmedi,
  SHARED_ALLOCATION_STATUS = future_dev.
- ADIM 57 ürün koduna dokunmadı: iki bloklayıcı ajan hook'unu (guard-git.sh,
  guard-generated.sh) .claude/settings.json'a doğrudan bağladı — plugin remote'ta
  KURULMUYOR (onay istemi gerekir, container etkileşimsiz). Yeni kapı:
  scripts/hook-guard-proof.sh, `Frontend` job'ında ADIM olarak.
- P1-Gate3 KAPANMADI (A=1 · B=80 · C=6 · D=32, açık 119).

SIRADAKİ İŞ — seçeneklerden birini seç ve GEREKÇESİNİ YAZ:
(a) `## Next` ana ekseni: PR B — ItemParticipant adaptörü +
    jobs/backtest_engine.py:298 call site. ADR §16 İNSAN KAPISI + ADR amendment'ı
    gerektirir; o kapıdan geçmeden başlama (docs/ADIM35_LANDED_KICKOFF.md §4.1).
(b) Kabul borcu sınıf B, parti 04. PARTİ SEÇMEDEN ÖNCE ÖLÇ: kriterin adlandırdığı
    davranış backend/src'te sevk edilmemişse sınıfı yanlıştır (ADIM 52/54 dersi).
    Sınıfı değiştirmek bir adjudication'dır — tavanı YÜKSELTİR, test slice'ının
    kararı değil.
(c) RC §6.7'de kalanlar: P11-6b · P11-3b · P8-B3b · P4-3 · P10-B6 · P10-B3/B4/B5.

KURALLAR:
- Yeni CI job'ı EKLEME (ruleset 20765617 — üretilmeyen required ad tüm merge'leri
  kilitler). Var olan job'a ADIM ekle.
- Ratchet YALNIZ AŞAĞI iner; eşik düşürme, kriter silme yok.
- Her CRITICAL/HIGH code-review bulgusunu düzeltmeden ÖNCE ampirik doğrula.
- Bash çağrıların artık guard-git.sh'ten geçiyor: "git push --force … main",
  self-merge ya da bu desenleri İÇEREN bir heredoc/döngü bloklanır. Metni Write ile
  dosyaya yaz, dosyayı koştur.
- Kapanışta CLAUDE.md ritüelinin altı çıktısı; md. 4 türetilir:
  node scripts/memory_index.mjs --sync --only <slug>.
```
