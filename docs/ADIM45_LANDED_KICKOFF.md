<!-- doc-status: current -->

# ADIM 45 landed — RC blocker 2 KAPANDI (`flows` artık bir CI kapısı) · sonraki oturum kickoff

**Base:** `origin/main` @ `853a358` · **Dal:** `ci/rc-blocker2-flows-gate` · **PR:** #680
**Ürün kodu değişmedi.** Migration yok · `ENGINE_VERSION` aynı · alembic head
`0043_i08_registry_strategy_fks`.

---

## Neredeyiz

**Blocker sayısı 2 → 1. Geriye YALNIZ A-08 kaldı. Verdict hâlâ `BLOCKED`.**

RC §6.2'nin açık kalan tek ekseni ("`flows` bir CI kapısı değildir") kapandı:
`e2e.yml`'e **`acceptance-flows`** job'ı eklendi ve **gerçekten koştu** —
job **94097720164**, **`67 passed / 0 failed / 1 skipped`**, `duration_seconds=137`,
job wall-clock **2m56s**, tarayıcı katmanı **5 passed**.
Kanıt: `docs/releases/evidence/2026-08-12/` (`P6B2_flows_ci_gate.md` + üç ham dosya).

---

## Bu slice'ın geride bıraktıkları — REUSE ANCHORS (tam sembol adlarıyla)

| Sembol / dosya | Ne işe yarar |
|---|---|
| `.github/workflows/e2e.yml::acceptance-flows` | kapının kendisi; `scripts/e2e-acceptance.sh flows` koşar |
| `scripts/e2e-acceptance.sh` skip-ceiling bloğu (dosya sonu) | `E2E_MAX_SKIPS` — karara bağlanmış skip tavanı |
| `scripts/lib/acceptance-flows.sh::af_flow_c_esp_lifecycle_export` | `[c2]`/`[c5]` pinleri + yapısal SKIP gerekçesi |
| `scripts/lib/acceptance-flows.sh::af_flow_d_agent_signal_tools` | `[d5]` Coordinator bekleyişi + Tool Gateway günlüğü; `[d6]` runtime kapısı |
| `docs/releases/evidence/2026-08-12/p6b2_esp_vector_local_proof.txt` | Docker'sız, sevk edilmiş doğrulayıcıya karşı üretilen ESP kanıtı |

---

## Bir dahaki sefere BİLMEN GEREKENLER (bunlar acıtır)

* **`E2E_MAX_SKIPS` bir sayı değil, bir KARARDIR.** CI'da **1**. Yeni bir `af_skip`
  eklersen kapı kırmızıya döner — **tavanı yükselterek geçme**; ya adımı geri getir ya da
  RC §6.2'de gerekçesini yaz, tavan **oradan** yükselir. Hata mesajı bunu söyler.
* **`[c2]`'nin `validation_state=failed` pini bilerek konmuştur.** `af.probe.rc.v1`
  `VALIDATABLE_RESOLVER_KEYS`'de olmadığı için doc 09 §7 onu **kanıtı tam olsa bile**
  reddetmek zorundadır. Burası `passed` okursa **bir ürün değişikliği olmuştur** ve
  `[c5]`'in yapısal SKIP kararı **yeniden açılmalıdır** — testi düzeltip geçme.
* **Pozitif ESP `activate`→`deprecate` kesişimi BOŞ.** (1) yalnız altı kanonik anahtar
  doğrulanabilir, (2) `seed.py::_ESP_TA_RESOLVERS` altısını da `trusted_active` tohumlar,
  (3) aktivasyon yalnız `candidate`'ten yasaldır. **Kanonik bir anahtarı deprecate ederek
  yer açmaya ÇALIŞMA** — `deprecated` terminaldir ve o anahtar bir daha asla
  trusted-active olamaz; üstelik tarayıcı katmanının Pre-Check'ini kırarsın.
* **`set -o pipefail` + `|| rc=$?` ikisi de taşıyıcı.** `pipefail` olmadan adım **tee'nin**
  exit code'unu alır ve düşen bir kabul koşusu **yeşil** raporlar. `|| rc=$?` olmadan
  runner'ın `bash -e`'si adımı anında öldürür ve **duration satırı kaybolur** — tam da
  sayının en çok gerektiği koşuda. İkisini de kaldırma.
* **Harness'ın kendi `npx playwright install chromium`'u `--with-deps` KULLANAMAZ** (root
  ister). Job onu **önceden** kurar; o adımı silersen tarayıcı katmanı sessizce SKIP'e
  düşer — ve `E2E_MAX_SKIPS` bunu kırmızıya çevirir (öyle olmalı).
* **Concurrency: yeni bir workflow AÇMA.** Job `e2e.yml`'de duruyor ki **zaten doğru olan**
  bloğu miras alsın. Ayrı bir workflow kendi `concurrency:`sini ister — `e8d1d48`/`bc59dae`
  (`total_jobs=0`, cancelled) kusurunun geri gelmesi için ikinci bir şans.
* **Yeşil rozet kanıt değildir.** Bir kapının koştuğunu **job log'undan** doğrula. Bu
  slice'ta ilk sinyal 2m56s'lik "çok hızlı" bir yeşildi; log okunmadan kabul edilmedi
  (yığın gerçekten kalkmıştı: seed PASS + yedi düzlem healthy).

---

## Sıradaki iş (öncelik sırasıyla)

1. **PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.**
   ADIM 35 §4.1'in **(c)** engelini kapattı (projeksiyon var); kalan **(a)** faz-bölünmüş
   bar ve **(b)** book-etmeyen değerlendirme girişi `run_engine`'in gövdesine dokunur →
   **ADR §16 insan kapısı + ADR amendment'ı** gerekir. O kapıdan geçmeden başlama.
2. **A-08 denetimi (blocker 1, TEK kalan blocker).** #514 **yeniden AÇIK**; yığın 9/9
   doğrulanmış, runbook yazılmış. **Denetimi bir insan koşar**; agent ne koşabilir ne de
   #514'ü kapatabilir. Defter: `docs/audit/a11y_screen_reader_audit_results.md`.
3. **P11-1 branch protection** — insan/depo kararı. Bu slice'ın kapısı required status
   check yapılmadıkça merge'i durdurmaz.
4. RC §6.5 K-2..K-7 · §6.6 issue hijyeni · §6.7'nin kalan kalemleri (P8-B3b, P10-B2'nin PO
   yarısı, P11-6b, #677'deki donmuş Lighthouse kusurları).

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 46

[[ ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ / PR DİSİPLİNİ
   bloklarını buraya aynen yapıştır ]]

BASE: origin/main (DOĞRULA — `git fetch && git log --oneline origin/main -6`;
ADIM 45 / PR #680 merge edilmiş olmalı)

NEREDE KALDIK
  ADIM 45 RC blocker 2'yi KAPATTI: scripts/e2e-acceptance.sh flows artık
  .github/workflows/e2e.yml::acceptance-flows olarak BLOKLAYICI bir CI kapısı
  (job 94097720164 → 67 passed / 0 failed / 1 skipped, duration_seconds=137).
  Blocker sayısı 2 → 1. GERİYE YALNIZ A-08 KALDI. Verdict hâlâ BLOCKED.
  Ayrıntı: docs/ADIM45_LANDED_KICKOFF.md · docs/PROJECT_HISTORY.md §ADIM 45 ·
  RC readiness §6.2 · docs/releases/evidence/2026-08-12/P6B2_flows_ci_gate.md

BU ADIMIN İŞİ
  [[ aşağıdakilerden BİRİNİ seç ve buraya yaz ]]
  (a) PR B — ItemParticipant adaptörü + jobs/backtest_engine.py:298 call site.
      ÖNCE ADR §16 insan kapısı + ADR amendment'ı; o kapıdan geçmeden başlama.
  (b) RC §6.7 kalan kalemleri (P8-B3b · P10-B2'nin PO yarısı · P11-6b · #677).
  (c) RC §6.5 K-2..K-7 (ölçüldü, düzeltilmedi; K-5/K-7 koşudan koşuya oynuyor —
      precheck'i EN AZ İKİ KEZ koş, ilk koşu soğuktur ve eksik raporlar).

TAVİZ VERİLEMEZ
  · A-08 (#514) İNSAN KAPISI — durumunu DEĞİŞTİRME, issue'yu KAPATMA.
    2026-08-12'de bir insan tarafından yeniden AÇILDI; defter hâlâ boş.
  · E2E_MAX_SKIPS bir karardır. Yeni skip → tavanı yükseltme; RC §6.2'de
    gerekçelendir ya da adımı geri getir.
  · [c2]'nin validation_state=failed pini ürün değişikliği dedektörüdür —
    kırmızıya dönerse testi düzeltip geçme, [c5]'in SKIP kararını yeniden aç.
  · Yeni workflow açma; concurrency bloğu miras alınıyor.
  · Kapıyı advisory yapma. Yeşile zorlama YOK. "READY" YAZMA.
  · Yeşil rozet kanıt değildir — job LOG'unu oku.

KAPANIŞ
  · CLAUDE.md §Session CLOSING ritüelinin 6 maddesi
  · cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
  · git diff origin/main -- docs/ | grep '^-## '   → BOŞ olmalı
```
