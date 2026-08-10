<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı). Canlı kickoff: `docs/ADIM34_LANDED_KICKOFF.md`.

# ADIM 32 landed — kickoff for the next session

**Ne indi:** RC readiness raporu §6.7'nin **P9-F2** kalemi — *"SPA origin'inde CSP yok."*
Yürütülebilir bundle'ı sunan origin artık bir Content-Security-Policy veriyor, politika
**canlı yanıt üzerinde** bir kapıyla pinlendi ve kapı CI'a bağlandı.

**Ne İNMEDİ:** ürün kodu. `backend/src` ve `frontend/src` bu dalgada **hiç düzenlenmedi**;
migration yok, lockfile değişmedi, `ENGINE_VERSION` sabit, `SHARED_ALLOCATION_STATUS` =
`future_dev`. Route path, react-query key, OCC token, Idempotency-Key, hook, SSE
taksonomisi, `lib/*.ts` **dokunulmadı**. **Blocker sayısı DEĞİŞMEDİ (üç); RC verdict'i
BLOCKED kalır.** P9-F2 blocker değildi.

---

## 1. Nerede duruyoruz

- **RC verdict BLOCKED**, üç blocker açık: (1) **A-08** insan denetimi · (2) kabul akışları
  `flows` **CI kapısı değil** · (4) **react-router** imzasız freeze. Üçü de **insan işidir**.
- **P9-F2 KAPANDI** (§6.7.1). Kapanmayan komşuları: **P9-F1** (`npm install` → `npm ci`) ve
  **P11-1** (branch protection yok) — **ayrı PR'lar**, ve P11-1 zaten **repo ayarı / insan
  kararı**.
- Motor yolu **hâlâ açık**: `run_portfolio` üretimde çağrısız, `jobs/backtest_engine.py:298`.

## 2. Bu slice'ın bıraktığı REUSE anchor'ları (tam sembol adlarıyla)

| Anchor | Nerede | Ne için |
|---|---|---|
| `EXPECTED_HEADERS` | `scripts/spa-security-headers-gate.sh` | `name\|exact-value` listesi. **Yeni bir güvenlik header'ı eklerken yalnız buraya satır ekle** — iki yüzey de otomatik kapsanır. |
| `header_of()` | aynı dosya | Ham header dump'ından değer okur. **bash 3.2 uyumlu** (assoc-array YOK) — macOS'ta da koşar. |
| `assert_surface()` | aynı dosya | Bir URL'yi çeker, 200 doğrular, tüm header'ları birebir karşılaştırır. Üçüncü bir yüzey eklemek = bir çağrı. |
| `__API_ORIGIN__` | `frontend/nginx-security-headers.conf` + `frontend/Dockerfile` | Build-time substitution sözleşmesi. Yer tutucu hayatta kalırsa **build durur**. |
| `SecurityHeadersMiddleware` | `backend/src/entropia/apps/api/hardening.py` | API tarafının **ayrı** politikası (`default-src 'none'`). İkisi kasten farklıdır: API JSON döner, hiçbir şey yürütmez. **Birleştirme.** |
| `test_security_headers_ride_every_response` | `backend/tests/contract/test_hardening_contract.py` | API'nin canlı-yanıt CSP testi — bu slice'ın **şablonu**. |

## 3. ÖLÇÜLMÜŞ TUZAKLAR — bir daha düşme

1. **"Config'de yazıyor" ≠ "yanıtta var".** SPA origin'inin dört header'ı **aylardır** bir
   config dosyası + düzyazı olarak sevk ediliyordu ve **hiçbir zaman telden okunmamıştı**.
   Yeni bir header eklerken kapıyı da ekle, yoksa aynı boşluk tekrar açılır.
2. **`location /assets/` header'ları İPTAL EDER.** Kendi `add_header`'ını bildiren her
   location bloğu, sunucu düzeyindeki **tüm** `add_header`'ları iptal eder. Bu regresyon bu
   repoda **gerçekten sevk edildi**. Kapı bu yüzden hash'li bundle'ı ayrıca sorgular.
3. **Login sayfasına bakıp "çalışıyor" deme.** İlk yüklenen sayfada (unauthenticated shell)
   **sıfır** inline style vardı — yani 814 React `style={{}}` prop'unun CSP altında hayatta
   kalıp kalmadığı sorusunu o sayfa **hiç sormaz**. Cevap kimliği doğrulanmış sayfalarda:
   9 route, **101** inline-style'lı öğe, **0 ihlal**.
4. **CSP "mevcut" olabilir ama uygulanmıyor olabilir.** Bunu varsayma — canlı sayfada
   enjekte bir inline `<script>`'in **çalışmadığını** ölç. Ölçüldü: çalışmadı.
5. **`pytest … | tail` KULLANMA** ve alt küme koşarken `--no-cov` ekle (repo'nun eski
   yarası; bu dalgada backend suite'i zaten koşulmadı — kaynak değişmedi).

## 4. Kapanmayan artıklar — bir sonraki slice bunları KAPATMAK ZORUNDA DEĞİL, ama BİLMELİ

- Kapı yalnız `install-acceptance.yml` → `fresh-install`'ta koşar (`e2e.yml`'de değil).
- **P11-1 açık** olduğu sürece bu kapı da **required status check DEĞİL**, job kapısıdır.
- CSP **`report-uri`/`report-to` taşımıyor** — production'da gerçek bir ihlal hiçbir yere
  raporlanmaz. Toplayıcı uç yok; bu slice bir tane **uydurmadı**.
- Yalnız **cross-origin compose topolojisi** ölçüldü. Reverse-proxy arkasında same-origin
  sunulan kurulumda `connect-src` kendiliğinden daralır ama **o topoloji ölçülmedi**.
- `frontend/` altında **`.dockerignore` yok** → yerel `node_modules` build context'ine
  girer. CI etkilenmez (temiz checkout). **P9-F1 alanı.**

## 5. Çalışma yöntemi (bu slice'ta işe yaradı, tekrar et)

**Önce ölç, sonra yaz.** Politikanın her direktifi `dist/`'ten okunan bir sayıya dayanıyor
(inline script 0, `eval` 0, `data:` 0, harici URL 0). Bu yüzden `unsafe-*` yok ve olmadığı
**kanıtlanabilir**. **Sonra kapıyı kırmızıya döndür** — geçen bir kapı, ısırdığını
kanıtlamaz. **Sonra uygulamayı gerçekten koştur** — e2e yeşil + console'da sıfır ihlal.

## 6. Next

**Değişmedi:** **PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.**
ADIM 25/26/27/30/31/32 ops/CI/harness/docs/güvenlik dalgalarıydı; hiçbiri motor yoluna
dokunmadı. `run_portfolio` hâlâ çağrısız, `SHARED_ALLOCATION_STATUS` = `future_dev`.

Ayrıca hâlâ bekleyen: **yarım-cent yuvarlama** kararı uygulanmadı
(`STAGE2_HANDOFF.md` §Yarım-cent) · **A-08** (insan) · **react-router freeze imzası** (insan)
· **P9-F1** (`npm ci` + `.dockerignore`) · **P11-1** (branch protection — insan).

---

## 7. Paste-ready resume prompt

```
ENTROPIA V18 — bir sonraki slice

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — ADIM 32 merge oldu mu, SHA ne?)

OTURUM BAŞLANGICI
  · git fetch && git log --oneline origin/main -6 && gh pr list --state all
  · docs/ADIM32_LANDED_KICKOFF.md (bu dosya) → docs/STAGE2_HANDOFF.md §ADIM 32 →
    docs/STAGE_BUILD_PLAN.md → ilgili docs/spec/NN_*
  · Kod tarafına geçmeden docs/CODEMAPS/ haritasını oku, sonra codebase-memory-mcp.

NEREDE DURUYORUZ
  · RC verdict BLOCKED, üç blocker açık: (1) A-08 insan denetimi · (2) kabul
    akışları `flows` CI kapısı değil · (4) react-router imzasız freeze.
    Üçü de İNSAN işidir; agent imza atamaz, issue kapatamaz.
  · P9-F2 (SPA CSP) ADIM 32'de KAPANDI. Politika `default-src 'none'` tabanlı,
    unsafe-* YOK, connect-src origin'i BUILD ZAMANINDA VITE_API_BASE_URL'den
    türetilir (yer tutucu kalırsa build durur).
    Kapı: scripts/spa-security-headers-gate.sh — CANLI YANITI assert eder,
    config dosyasını DEĞİL; `/` VE hash'li bundle'ı sorgular.
    CI: install-acceptance.yml → fresh-install, negatif adımıyla birlikte.
  · KAPANMAYAN ARTIK: kapı yalnız o job'da koşar · P11-1 açık olduğu için
    required status check DEĞİL · CSP report-uri/report-to taşımıyor.

PLANLI NEXT: PR B — `ItemParticipant` adaptörü + jobs/backtest_engine.py:298
call site. (ADIM 21 (worker delivery) ile KARIŞTIRMA — başlık ekleri kuraldır.)

TAVİZ VERİLEMEZ
  · Ürün kodu değişiyorsa: backend tam suite tek pytest çağrısında, coverage
    kapısı ≥90 (alt küme koşarken --no-cov), L1 FK insert-order proof'u,
    alembic up/down/up, migration↔model kolon paritesi.
  · Güvenlik header'ı eklersen kapıyı da ekle — "config'de yazıyor" ile
    "yanıtta var" AYNI ŞEY DEĞİLDİR, ve bu repo tam olarak buna düştü.
  · Sahte yeşil üretme: bir kapının ölçtüğü şeyi, ölçmediği şey sanma.
  · İmza, issue kapatma, tag, release → İNSAN. Agent yapamaz.
```
