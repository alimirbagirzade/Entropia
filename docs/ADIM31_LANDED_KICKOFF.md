<!-- doc-status: current -->

# ADIM 31 landed — kickoff for the next session

**Ne indi:** RC blocker 3 — **fail-closed alarm bildirim yolu**. ADIM 25/26'nın doğrulanmış
11 alarm kuralı artık bir insana **ulaşıyor**, ve hedef adres verilmezse Alertmanager
**başlamıyor**.

**Tip:** ops/CI. `backend/src` ve `frontend/` **düzenlenmedi**. Migration yok, lockfile
değişmedi, `ENGINE_VERSION` sabit, `SHARED_ALLOCATION_STATUS` = `future_dev`. İmza yok,
tag yok, release yok, issue açılmadı/kapatılmadı.

---

## 1. Nerede duruyoruz

| Blocker | Durum |
|---|---|
| 1 — A-08 insan ekran okuyucu kabul denetimi | **AÇIK** (insan işi: #514'ü yeniden aç **veya** D-10 biçimi imzalı sapma) |
| 2 — kabul akışları | **KISMEN** (ADIM 30: beş akış koştu; `flows` **CI kapısı değil** — insan maliyet kararı) |
| ~~3 — Alertmanager~~ | **KAPANDI (ADIM 31)** |
| 4 — react-router imzasız freeze | **AÇIK** (imzalayan verilmediği için agent yazamaz) |

**RC verdict'i `BLOCKED` KALIR.** Blocker sayısı **4 → 3**. Numaralandırma **bilerek
korunmuştur** — kalanlar (1), (2), (4) olarak anılmaya devam eder; yeniden numaralandırmak
bu belgeye atıf yapan merge edilmiş PR gövdelerini geçmişten koparırdı.

---

## 2. Bu slice'ın bıraktığı REUSE anchor'ları (tam sembol adlarıyla)

| Sembol / dosya | Ne yapar — ve neden yeniden kullanılmalı |
|---|---|
| `ops/alertmanager/alertmanager.yml` | Routing ağacı. **Yeni bir severity eklerken** buraya bir route ekle; `test_every_severity_the_rules_emit_has_a_route` aksi halde kırmızı verir |
| `ops/alertmanager/entrypoint.sh::require_url` | Fail-closed kapısı. **Yeni bir zorunlu ops env var'ı** için deseni buradan kopyala (unset/boş/şema kontrolü → `exit 78` + değişkeni adıyla anan mesaj) |
| `ops/prometheus/entrypoint.sh` | Read-only mount'tan **birebir `cp -R` stage** deseni. Şablonlama provenance hash'ini kırar — dokunma |
| `scripts/alert-notification-gate.sh` | `mktemp -d` + `chmod -R a+rX` + digest-pinned image deseni (`alert-rules-gate.sh` ile aynı; macOS'ta yeşil, CI'da kırmızı olan sahiplik tuzağı ikisinde de belgeli) |
| `scripts/alert-notification-proof.sh` | 4 fazlı uçtan uca kanıt. **Bağımlılıksız** (bash + docker); PyYAML/jq gerektirmez — kanıtı yeniden üretecek operatörün ortam kurması gerekmez |
| `ops/alertmanager/notification_catcher.py::MARKER` | Test receiver'ın grep'lenen işareti. Yeniden adlandırmak proof'u **sessizce** "hiçbir şey gelmedi"ye çevirir — o yüzden sabit |
| `backend/tests/contract/test_alert_notification_contract.py` | 21 yapısal test. **Yeni receiver eklerken** hepsi geçmeli: notifier config'siz receiver yok, inline `url` yok, page↔ticket çakışmaz, kök receiver gerçek |
| `docker-compose.yml` `profiles: ["observability"]` | **Yeni bir opsiyonel servis** eklerken bu deseni kullan — düz `docker compose up` üç kabul script'inin yığınıdır ve değişmemeli |

---

## 3. ÜÇ ÖLÇÜLMÜŞ TUZAK — bir daha düşme

1. **`GET /api/v1/status/config` byte-diff'i ASLA geçmez.** Prometheus config'i *marshalled*
   döndürür: `scrape_protocols`, `runtime.gogc` gibi varsayılanlar enjekte edilir, tüm
   yorumlar silinir. İlk yazılan provenance kapısı bu yüzden kırmızı verdi — **kapının**
   tasarım hatasıydı. Yerine geçen zincir: sha256 (çalışma ağacı = mount = staged) +
   `--config.file` flag'i + parse edilmiş değerler + kural seti diff'i.
2. **`amtool check-config`, notifier config'i OLMAYAN bir receiver'a SUCCESS döner**
   (v0.28.1'de ölçüldü). "Geçici placeholder receiver" tam olarak bu şekildir. Kapı yeşil
   kalırken her alarm sessizce düşer.
3. **`docker compose logs | grep -q`, `set -o pipefail` altında tuzaktır.** grep ilk
   eşleşmede çıkar → docker SIGPIPE → pipeline başarısız görünür. **Gerçekleşmiş bir
   teslimat "gelmedi" diye okundu** (proof exit 255, bildirim çoktan alıcıdaydı). Log'u
   **önce dosyaya yaz**, sonra grep'le.

---

## 4. Kapanmayan artıklar — bir sonraki slice bunları KAPATMAK ZORUNDA DEĞİL, ama BİLMELİ

| # | Artık | Kim kapatabilir |
|---|---|---|
| **1** | **Kurallar gerçek production serilerine karşı hiç değerlendirilmedi.** Yalnız sentetik seri + tek yapısal `up == 0`. Yanlış ayarlanmış bir eşik hâlâ *doğru* görünür | Yalnız gerçek trafik. **Repo içinde kapatılamaz. İmzalı sapma DEĞİLDİR** — süreli kayda dönüştürülmesi istenirse **imzayı agent atayamaz** |
| **2 (P10-B3)** | Delivery proof'u **CI kapısı değil** — config yarısı kapılı, teslimat yarısı değil | İnsan (maliyet kararı: üç konteyner + dakikalar, her PR'da) |
| **3 (P10-B4)** | **Monitörü izleyen yok** — `prometheus_notifications_errors_total` Prometheus'un kendi `/metrics`'inde, onu kimse scrape etmiyor | Döngüsel olmayan çözüm ikinci bir Prometheus ister |
| **4 (P10-B5)** | **On-call rotasyonu / escalation / acknowledgement yok.** Alertmanager'ın ack kavramı yoktur; `repeat_interval` mekanizmanın tamamıdır | Organizasyonel, repo dışı |
| **5** | **Kuyruk bazında worker liveness gözlemlenemiyor** (`METRIC_ALERT_MATRIX.md` §4) — ölü bir `worker-backtest` heartbeat'i taze bırakır | Yeni bir **metrik**, yeni bir receiver değil |

Tam liste ve gerekçeleri: **`docs/runbooks/alert-notification.md` §5**.

---

## 5. Çalışma yöntemi (bu slice'ta işe yaradı, tekrar et)

* **Raporun sayılarını kopyalama, yeniden ölç.** §6.3'ün beş iddiası `origin/main` üzerinde
  yeniden üretildi (`p10b_preexisting_state.txt`); beşi de doğru çıktı — ama madde 3'ün ham
  çıktısı iddiayı çürütür *görünüyordu* (üç dosya eşleşiyor). Hit'leri satır satır basmak
  farkı gösterdi: hepsi **yokluğu anlatan yorum**. Dosya listesi değil, hit'ler kanıttır.
* **Kapının ölçtüğü şeyi, ölçmediği şey sanma.** Bu dalganın tamamı bunun üzerine kuruldu:
  yeşil `Alert rules — promtool` rozeti "alarm sistemi çalışıyor" demek değildi. CI job'ı bu
  yüzden **yeniden adlandırıldı** (`Alert rules and notification path`).
* **Fail-closed'ı bir teste değil, davranışa bağla.** Contract testi launcher'ın *kaynağını*
  okur (`require_url`, `exit 78`, `:-` varsayılanı yok); proof faz 1 *davranışı* ölçer. İkisi
  ayrı ayrı yanılabilir, birlikte yanılamaz.

---

## 6. Next

**Değişmedi:** **PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.**
ADIM 25/26/27/30/31 ops/CI/harness/docs dalgalarıydı; hiçbiri motor yoluna dokunmadı.
`run_portfolio` hâlâ üretimde **çağrısız**, `SHARED_ALLOCATION_STATUS` = `future_dev`.

Ayrıca hâlâ bekleyen: **yarım-cent yuvarlama** kararı uygulanmadı
(`STAGE2_HANDOFF.md` §Yarım-cent) · **A-08** (insan) · **react-router freeze imzası** (insan).

---

## 7. Paste-ready resume prompt

```
ENTROPIA V18 — bir sonraki slice

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — ADIM 31 merge oldu mu, SHA ne?)

OTURUM BAŞLANGICI
  · git fetch && git log --oneline origin/main -6 && gh pr list --state all
  · docs/ADIM31_LANDED_KICKOFF.md (bu dosya) → docs/STAGE2_HANDOFF.md §ADIM 31 →
    docs/STAGE_BUILD_PLAN.md → ilgili docs/spec/NN_*
  · Kod tarafına geçmeden docs/CODEMAPS/ haritasını oku, sonra codebase-memory-mcp.

NEREDE DURUYORUZ
  · RC verdict BLOCKED, üç blocker açık: (1) A-08 insan denetimi · (2) kabul
    akışları `flows` CI kapısı değil · (4) react-router imzasız freeze.
    Üçü de İNSAN işidir; agent imza atamaz, issue kapatamaz.
  · Blocker 3 (Alertmanager) ADIM 31'de KAPANDI. Bildirim yolu fail-closed'dur:
    ALERTMANAGER_NOTIFY_URL yoksa Alertmanager exit 78 verir, başlamaz.
  · KAPANMAYAN ARTIK: kurallar gerçek production serilerine karşı hiç
    değerlendirilmedi. Bu bir imzalı sapma DEĞİLDİR ve repo içinde kapatılamaz.

PLANLI NEXT: PR B — `ItemParticipant` adaptörü + jobs/backtest_engine.py:298
call site. (ADIM 21 (worker delivery) ile KARIŞTIRMA — başlık ekleri kuraldır.)

TAVİZ VERİLEMEZ
  · Ürün kodu değişiyorsa: backend tam suite tek pytest çağrısında, coverage
    kapısı ≥90 (alt küme koşarken --no-cov), L1 FK insert-order proof'u,
    alembic up/down/up, migration↔model kolon paritesi.
  · Sahte yeşil üretme: bir kapının ölçtüğü şeyi, ölçmediği şey sanma.
  · İmza, issue kapatma, tag, release → İNSAN. Agent yapamaz.
```
