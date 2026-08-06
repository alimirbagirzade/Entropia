# ADIM 26 kapanış devri — alert kuralları artık GERÇEKTEN doğrulanıyor

> **Durum uyarısı:** bu belge yazıldığında **PR #624 AÇIK, merge EDİLMEMİŞTİ.**
> "landed" yazmıyorum çünkü inmedi. Yeni oturuma başlarken **önce doğrula**:
> `gh pr view 624 --json state,mergedAt`. Merge edilmediyse aşağıdaki her şey
> hâlâ bir dal üzerindedir.

## Nerede duruyoruz

ADIM 25, 11 alert kuralını **hiçbir PromQL doğrulaması olmadan** sevk etti.
Bedeli ölçüldü: iki paging kuralı `up{...} == 1 and absent(...)` biçiminde çıktı —
parse oluyor, yükleniyor, kapsam gibi görünüyor ve **hiç ateşlenemiyor**
(`absent()` etiketsiz eleman döner, `and` tüm etiket kümesini eşleştirir).
Onu bir kapı değil, insan review'ı yakaladı.

ADIM 26 tam olarak bu boşluğu kapattı, **başka hiçbir şeye dokunmadan**.

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam sembol adlarıyla)

| Anchor | Ne yapar |
|---|---|
| `scripts/alert-rules-gate.sh` | `promtool check config` → `check rules` → `test rules`. Digest-pinned `prom/prometheus@sha256:63805ebb…` (v3.5.0 LTS). Tek bağımlılık: docker. |
| `ops/prometheus/prometheus.yml` | `job_name: entropia-api` — dört kuralın bağlı olduğu adı **kontrol edilebilir bir olgu** yapar. `rule_files` ve `credentials_file` **göreli** (Prometheus bunları config dosyasının kendi dizinine göre çözer), böylece `ops/` tek parça taşınır. |
| `ops/alerts/entropia.rules.test.yml` | 15 promtool unit-test case'i. Assertion'lar **`alert_rule_test` değil, sentetik `ALERTS{...}` serisi** üzerinde — çünkü `alert_rule_test` anotasyonları **tam** karşılaştırır ve her beklenen alert dokuz operatör anotasyonunu birebir tekrar yazmak zorunda kalırdı. Bu kopya kaçınılmaz olarak sapardı ve **sapma, geçen bir test gibi görünürdü**. |
| `test_every_alert_has_an_evaluated_firing_case` | Değerlendirilmiş bir firing case'i olmayan kuralı reddeder — ucuz metin kapısının gerçek PromQL kapısını geçmesini engeller. |
| `test_every_job_matcher_names_a_declared_scrape_job` | `job=` eşleştiricisi scrape config'in bildirmediği bir job'ı adlandırırsa build kırmızı. |
| CI job `Alert rules — promtool` | Paralel koşar → eklenen wall-clock **0**. Ölçüm: 43 sn soğuk / 14 sn CI'da. |

## Kapı kendi kendine test edildi (4 kanıt, hepsi geri alındı)

| # | Enjekte edilen kusur | Sonuç |
|---|---|---|
| A | `on()` silindi — **tam olarak ADIM 25 kusuru** | `check rules` **SUCCESS: 11 rules found**, `test rules` **FAILED — `got: nil`** |
| B | Geçersiz PromQL (`>> 1200(`) | `check rules` FAILED `213:15 … unexpected <op:>>` |
| C | Scrape job `entropia-backend` yapıldı | 2 contract testi kırmızı, 4 etkilenen kuralı adıyla söyler |
| D | Bir firing assertion'ı `pending`'e düşürüldü | `test_every_alert_has_an_evaluated_firing_case` kırmızı |

## Öğrenilen ders — TEKRARLAMA

**Kapı yerelde yeşil, CI'da kırmızıydı.** `mktemp -d` 0700 izinli, çağıran
kullanıcıya ait bir dizin üretir; resmi Prometheus imajı **`nobody` (uid 65534)**
olarak koşar ve dizine giremez → `stat /ops/prometheus/prometheus.yml: permission
denied`. **macOS bunu tamamen gizler** — Docker Desktop sahipliği VM üzerinden
eşler, `chmod 700` + `--user 65534` ile bile yerelde hata ÜRETİLEMEDİ.
Düzeltme `chmod -R a+rX "$workdir"` ve **placeholder token yazıldıktan SONRA**
(0600 bir credentials dosyası aynı hatayı bir adım sonra verir).
**Kural:** konteyner içinde koşan bir aracı bind-mount ile besliyorsan, izinleri
macOS'a güvenerek doğrulama — yalnızca Linux CI kanıtlar.

## Bilerek YAPILMAYANLAR (dürüst sınır)

* **Alertmanager / monitoring stack yok.** `docker-compose.yml`'ye Prometheus
  servisi eklenmedi ve `prometheus.yml` bilerek `alerting:` bloğu taşımıyor:
  repo Alertmanager sevk etmiyor, var olmayan bir routing'i reklam etmek yalan
  olurdu. **`severity: page` hâlâ hiçbir alıcının okumadığı bir etikettir —
  kurallar doğru ateşliyor ama kimseye ulaşmıyor.** Bu, `METRIC_ALERT_MATRIX.md`
  §4'te "Alert NOTIFICATION" satırı olarak kayıtlı.
* Kurallar **gerçek üretim serilerine** karşı hiç değerlendirilmedi — var olan
  ama pratikte hiç doldurulmayan bir metrik burada sağlıklı görünür.
* **Sevk edilen Prometheus'un gerçekten bu dosyadan yapılandırıldığını hiçbir
  kapı kanıtlamıyor.**

## Sıradaki tek adım — DEĞİŞMEDİ

**PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.**
ADIM 26 bir CI/ops doğrulama slice'ıydı; motor yoluna, migration'a, OpenAPI
yüzeyine ve frontend'e **dokunmadı**.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — PR B: `ItemParticipant` adaptörü + gerçek engine call site

ÖN KOŞUL (STALE-BY-DEFAULT — önce doğrula, özete güvenme)
`git fetch --all --prune`; `gh pr view 624 --json state,mergedAt` → ADIM 26
(promtool alert kapısı) merge oldu mu? `gh pr list --state all --limit 10` ve
`git log --oneline origin/main -8` ile gerçekten neyin indiğini teyit et.
Çalışma ağacı temiz, base = taze `origin/main`.

OKUMA SIRASI
1) `docs/ADIM26_LANDED_KICKOFF.md` (bu slice'ın devri)
2) `docs/STAGE2_HANDOFF.md` → "## Next"
3) `docs/STAGE_BUILD_PLAN.md` (stage tablosu + acceptance)
4) İlgili `docs/spec/NN_*` — spec'i TAM çıkar
5) Kod tarafına geçmeden `docs/CODEMAPS/BACKEND_LAYERS.md` + `JOBS_AND_EVENTS.md`,
   sonra `codebase-memory-mcp` ile sembolleri bul (kör grep YOK)

GÖREV
`ItemParticipant` adaptörünü yaz ve `jobs/backtest_engine.py:298` call site'ına
bağla. Önceki slice'ın desenini AYNEN aynala: module-level async command,
one-tx no-commit, `run_idempotent`, `session.refresh(with_for_update=True)`,
`_audit_and_outbox`. Direct-author — Workflow KULLANMA.

TAVİZ VERİLEMEZ
- `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI) — açma.
- Yarım-cent yuvarlama KARARA BAĞLI: `initial_sleeve_capital` yeniden quantize
  EDİLMEZ, dondurulmuş `derived_amounts`'tan KOPYALANIR; iki yuvarlama sabiti de
  değişmez. Henüz uygulanmadı — `STAGE2_HANDOFF.md` §Yarım-cent.
- Yeni mutating route eklersen gövdeyi typed model olarak bildir (`dict[str, Any]`
  dönüşü sözleşmeyi şemadan gizler) ve dual-token'ı route'a KOPYALAMA →
  `shared/concurrency.py::reconcile_occ_tokens`.

DOĞRULAMA
`cd backend && uv run ruff check . && uv run ruff format --check . &&
uv run mypy src && uv run pytest` — tam suite TEK çağrıda, çıktı dosyaya,
exit code AYRI okunur (`| tail` KULLANMA). Alt küme koşarken `--no-cov` ekle.
Paralel worktree varsa `TEST_DATABASE_URL` ile izole DB (`postgresql+asyncpg://`).
Her yeni `create_*` için L1 FK insert-order kanıtı + alembic up/down/up +
migration↔model kolon paritesi.

PR aç ve dur. Claude merge etmez.
```
