<!-- doc-status: historical -->
> **SUPERSEDED — ADIM 48 (2026-08-12).** Canlı kickoff artık
> `docs/ADIM48_LANDED_KICKOFF.md`. Aşağısı ADIM 47 kapanışındaki durumu kaydeder;
> sayıları ve "sıradaki iş" maddeleri bayat olabilir. **Özellikle:** bu belgenin
> A-08 / #514 hakkındaki *"izleme issue'su kapalı"* ifadesi **bayattır** — #514
> `2026-08-12T11:08:58Z`'de insan eliyle yeniden AÇILDI (ADIM 48).
> sayıları ve "sıradaki iş" maddeleri bayat olabilir.

# ADIM 47 LANDED — RC §6.7'nin iki PO kararı uygulandı · sıradaki slice için kickoff

> **Bu belge ADIM 47 kapanışında yazıldı.** Sayısal otorite bu belge DEĞİL →
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).
> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 47.

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.** ADIM 47 hiçbir kalemi READY'ye
çevirmedi; PO'nun 2026-08-12'de verdiği **iki** kararı uyguladı ve gerekçeleriyle kayda
geçirdi. Migration yok, `ENGINE_VERSION` değişmedi, OCC/Idempotency/route yolları/
react-query key'leri değişmedi. **OpenAPI bilerek değişti** (iki operation `200 → 202`,
iki component eklendi; path/operation sayısı aynı).

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam sembol adlarıyla)

| Anchor | Ne için |
|---|---|
| `apps/api/routes/create_package.py::ValidationRunAcceptedResponse` · `::BaselineParseAcceptedResponse` | YENİ tipli admission gövdeleri (8'er alan). **Yeni admission ucu eklerken şablon budur** — `dict[str, Any]` dönüşü sözleşmeyi şemadan gizler (O-30) |
| `tests/contract/test_p8b2_admission_status.py::_EXPECTED` | 13 admission ucunun status tablosu; küme `enqueue_job` transitive closure'ından **türetilir**. Sınıflandırılmamış yeni uç → kırmızı |
| `apps/api/pagination.py::clamped_limit_query` | Kelepçeli `limit`'in **TEK** declarator'ı; docstring PO kararının gerekçesini taşır |
| `tests/contract/test_pagination_limit_contract.py` | İki invariant **birlikte** kilitli: clamped → `x-clamp-maximum` VAR, JSON Schema `maximum` YOK |

## Tavizsiz kurallar (bu slice'ta kanıtlandı)

1. **`ALIGNED` ≠ `PO <tarih>`.** İlki kanonik kodu adlandırdığı için, ikincisi kanonik
   sessiz olduğu ve bir insan seçtiği için. `_EXPECTED`'te **birleştirme** — birleştiren
   okuyucu bir kararı atıf sanar ve karar yeniden açılabilirliğini kaybeder. Kanonik bir
   sayfa ileride bu uçlar için kod adlandırırsa **kanonik kazanır**.
2. **Sevk edilmiş desenden kanonik boşlukta wire contract TÜRETME.** 202 bu repoda
   "durable job" demek değildir (`agent-directives`, `.../cancel` de 202 döner ama
   `enqueue_job` çağırmaz). ADIM 47 uçları **PO kararıyla** çevirdi, desene bakarak değil.
3. **Bir ucu async'ten sync'e ya da tersine ÇEVİRME.** Status değişikliği yalnız sevk
   edilen semantiğin **adlandırılmasıdır**. Ölçtüğünde uç senkron çıkıyorsa **DUR ve raporla**.
4. **Kelepçeyi 422'ye çevirme.** PO kararı: kelepçe kalır. Sınır yayımlandığı için davranış
   sessiz değil; 422 bugün 200 dönen istekleri reddederek **üretilmiş istemcileri kırardı**.
5. **Sayı yazarken hangi ekseni saydığını söyle.** Kickoff'un *"§6.7'nin on iki kalemi"*
   iddiası yanlıştı çünkü iki ekseni (alt bölümler ↔ tablo) tek sayıya katlıyordu. ADIM 42
   dersinin tekrarı: bayat değil, **anlamsız** sayı.

## Açık kalanlar (ADIM 47 bunları KAPATMADI)

- **A-08 / #514** — tek kalan blocker; defter **boş** (0/4), izleme issue'su kapalı.
  **İnsan kapısı**, agent kapatamaz. Dokunulmadı.
- **`POST /library/{id}/validation-runs` = 201** — PO kararı onu **kapsamadı**; aynı
  validation run'ı saran iki uç hâlâ iki farklı status döndürüyor. **Yeni bir PO kararı ister.**
- **§6.7 tablosu: 24 satırda 10 AÇIK** — P4-3 · P10-B6 · P11-1 · P11-6b · P11-3b ·
  P8-B3b · P1-Gate3 · P10-B3 · P10-B4 · P10-B5. Yalnız P11-1 repo ayarıdır.
- **§6.7.N alt bölümleri: 12'de 11 kapalı** — **§6.7.10 / P1-Gate3** açık.
- **Memory checkpoint (ritüel md. 4) EKSİK** — bu oturumda `ecc` ve `claude-mem` MCP
  sunucuları bağlı değildi. **Bir sonraki oturumda yazılmalı.**
- **Tam suite yerelde koşmadı** — container'da Postgres yok (docker daemon kapalı);
  DB'ye bağlı testlerin otoritesi **CI'dır**.

## Sıradaki iş

Değişmedi: **PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py` item döngüsü
call site**. ADIM 35 §4.1'in **(c)** engelini kapattı; kalan **(a)** faz-bölünmüş bar ve
**(b)** book-etmeyen değerlendirme girişi `run_engine`'in gövdesine dokunur → **ADR §16
insan kapısı + ADR amendment'ı** gerekir, o kapıdan geçmeden başlama.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 48

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — `git fetch && git log --oneline origin/main -6`)
ADIM 47 landed: RC §6.7.9 (validate + baseline-parse → 202, PO kararı) ve §6.7.5
(kelepçe kalır, PO kararı) KAPANDI.

ÖNCE OKU (otorite sırası)
  1. docs/ADIM47_LANDED_KICKOFF.md (bu belge)
  2. docs/STAGE2_HANDOFF.md → "## Stage — ADIM 47" + "## Next"
  3. docs/PROJECT_HISTORY.md §ADIM 47
  4. docs/generated/repository_facts.md (SAYISAL OTORİTE — CLAUDE.md'deki sayı değil)

DURUM (doğrula, güvenme)
  · Blocker sayısı 1 (yalnız A-08), verdict BLOCKED. "READY" YAZMA.
  · §6.7 BİTMEDİ: tabloda 24 satırda 10 AÇIK (P4-3 · P10-B6 · P11-1 · P11-6b ·
    P11-3b · P8-B3b · P1-Gate3 · P10-B3/B4/B5); alt bölümlerde 12'de 11 kapalı.
  · `/library/{id}/validation-runs` 201'de KALDI — ayrışma açık, PO kararı ister.

ÖNCELİK: ilk iki maddeden BİRİNİ seç, ikisini birden alma
  (a) ADIM 47'nin EKSİK ritüel maddesi: ecc + claude-mem memory checkpoint'i
      (ADIM 47 oturumunda MCP sunucuları bağlı değildi). Önce bağlı mı ÖLÇ.
  (b) §6.7'nin açık kalemlerinden biri — P8-B3b (belge, düşük risk) ya da
      P10-B6 (4 uç etkin sayfa boyutunu yankılamıyor).
  (c) PR B (ItemParticipant) — ama ADR §16 insan kapısından geçmeden BAŞLAMA.

TAVİZ VERİLEMEZ
  · OCC (If-Match / expected_*_version / X-*-Version), Idempotency-Key, route
    YOLLARI, react-query key'leri, ENGINE_VERSION DEĞİŞMEZ.
  · Hata zarfı tek şekil (O-02): shared/responses.py::ErrorBody.
  · `_EXPECTED`'te ALIGNED ile PO etiketlerini BİRLEŞTİRME.
  · A-08 / #514'ün durumunu DEĞİŞTİRME — insan kapısı.
  · Yeşile zorlama YOK: kapı kırılıyorsa BLOCKED yaz.

ÖLÇÜM TUZAKLARI (bu repoda gerçekten yaşandı)
  · pytest'i | tail'e BORULAMA — exit code tail'in olur; çıktıyı dosyaya yaz, $?'i AYRI oku.
  · Alt küme koşarken --no-cov EKLE; tam suite TEK çağrıda, ortada öldürme.
  · vitest: --no-file-parallelism ZORUNLU.
  · TEST_DATABASE_URL ile izole DB; sürücü postgresql+asyncpg://
  · Postgres YOKSA (remote container) DB testleri koşmaz — otorite CI'dır, "geçti" YAZMA.
  · docs PR'ı öncesi: git diff origin/main -- docs/ | grep '^-## ' → BOŞ olmalı.

KAPANIŞ: CLAUDE.md §Session CLOSING ritüelinin 6 maddesi +
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
