<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 41 landed — devir belgesi (RC §6.7 / P8-B2, durable admission status)

**PR pending** · branch `fix/rc-p8b2-admission-status-adjudication` · base `0c3d0e6` (ADIM 40, #666).

> **Numaralandırma uyarısı.** Bu slice'a giden istem kendini **"ADIM 38b"** olarak adlandırıyordu.
> `origin/main` doğrulandığında ADIM 38 (#664), 39 (#665) ve 40 (#666) **zaten merge edilmişti**
> → numara yeniden kullanılmadı. Bu kayıt **ADIM 41**'dir. Merge edilmiş PR başlıkları
> değiştirilemez; yeniden numaralandırma belgeleri git geçmişinden ayırırdı.

---

## 1. Nerede duruyoruz

RC §6.7'nin **P8-B2** kalemi karara bağlandı — ama **KAPANMADI**: dört Create-Package
admission ucundan **ikisi hizalandı**, **ikisi PO kararı bekliyor**. Blocker değildi.
**Blocker sayısı üç, §8 verdict BLOCKED. P8 KAPANMADI.**

Yöntem kalemden daha önemli: **önce ayırt edici ölçüm, sonra kanonik, en sonda kod.**
"Tutarsızlık gördüm, hizalayayım" refleksi bilerek durduruldu — ve haklı çıktı: sapmanın
yarısının kanonik dayanağı vardı, yarısının **hiç yoktu**.

## 2. Bu slice'ın bıraktığı REUSE çapaları (tam sembol adlarıyla)

| Çapa | Ne işe yarar |
|---|---|
| `backend/tests/contract/test_p8b2_admission_status.py::_admission_commands` | `enqueue_job`'a transitively ulaşan application fonksiyonlarını **türetir**. Durable admission kümesine ihtiyacın olduğunda **elle liste yazma**, bunu kullan. |
| `…::_admission_routes` | O komutları route tablosuna eşler (sabit-isimli `_PURGE_PATH` gibi path'leri de çözer). |
| `…::_EXPECTED` | On üç ucun **adjudicated** status tablosu + her birinin gerekçesi. **Yeni admission ucu buraya girmeden CI yeşil olmaz.** |
| `routes/create_package.py::PrecheckAcceptedResponse` · `::CandidateAcceptedResponse` | 202 admission gövdelerinin tipli sözleşmesi. Yeni bir admission gövdesi yazarken **bare `dict` bırakma** (O-30). |
| `test_typed_contract_replay_parity.py::_stored_envelope` | `IdempotencyKey.response_ref` — "model alan düşürdü mü" sorusunun **hand-written olmayan** cevabı. |
| `docs/CODEMAPS/BACKEND_ROUTES.md` §DURABLE-ADMISSION STATUS | Kararın tek sahibi. Status tartışması çıkarsa **buraya** bak, spec'i baştan tarama. |

## 3. Ne öğrendik (bir sonraki adjudication için)

1. **Kanonik uç uç konuşur, sayfa sayfa değil.** `pre-check`'in status'ü doc 07'de,
   `generate-candidate`'inki **Master Technical Reference §7.1**'de literal wire contract
   olarak duruyordu; `validate`/`baseline-parse` için **hiçbir yerde yok**. Tek bir belgeye
   bakıp "kanonik sessiz" demek yanlış cevap verirdi.
2. **Sevk edilmiş desen ≠ kanonik kural.** 202 dönen beş uç (`agent-directives`,
   `agent-runtime/pause`·`/resume`, `agent-runs/{id}/stop`, `backtest-runs/{id}/cancel`)
   `enqueue_job` bile çağırmıyor. Desen gerçek ("etki yanıttan sonra iniyorsa 202") ama
   **kanonik boşlukta ondan wire contract türetilmez**.
3. **Raporun kendi sayısı da ölçülmelidir.** *"Diğer dokuz 202"* yanlıştı (8×202 + 1×201) ve
   yanlışlık bir yüzeyi (`/library/{id}/validation-runs`) görünmez kılıyordu.
4. **Status route'ta yaşar, idempotency zarfında değil.** `run_idempotent` yalnız gövdeyi
   saklar → status değişikliğinin O-30 tarzı bir backfill'i **yoktur**. Gövdeyi tiplerken
   ise vardır; bu yüzden alan-düşmezliği saklanan zarfa karşı kanıtlandı.

## 4. AÇIK kalemler (bu slice kapatmadı)

- **P8-B2'nin PO yarısı** — `../validate` + `../baseline-parse` + `POST /library/{id}/validation-runs`
  (201). Üç okuma ve öneri **rapor §6.7.9**'da yazılı. **Agent karar VERMEZ.**
- **P8-B3b** — `JOBS_AND_EVENTS.md` gövdesindeki ~30 `:NN`.
- **P11-6b** · **P11-8** · **P10-7** · **P10-B2'nin aşım davranışı** (clamp mı 422 mi — PO).
- **Genel status denetimi yapılmadı** — bu slice yalnız *durable admission* eksenidir.
- **AGENT İŞİ DEĞİL:** P11-1 (branch protection), üç blocker, A-08 kapatma kararı.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — <sıradaki slice>

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — ADIM 41 merge olmuş OLMALI; olmadıysa DUR.
      İstemdeki ADIM numarasına GÜVENME, `git log --oneline origin/main -8` +
      `gh pr list --state all` ile gerçek son slice'ı bul.)

ÖNCE OKU
  · docs/ADIM41_LANDED_KICKOFF.md (bu belge — REUSE çapaları §2, açık kalemler §4)
  · docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.7 tablosu + §6.7.9
  · docs/STAGE2_HANDOFF.md §ADIM 41 + §Next

AÇIK KALEMLER (birini seç, HEPSİNİ birden alma)
  · P8-B2 (PO yarısı) — ../validate + ../baseline-parse + /library/{id}/validation-runs.
             KARARI SEN VERME. §6.7.9'daki üç okumayı kullanıcıya sun, cevabı al,
             sonra uygula. Uygularsan: openapi snapshot + test_p8b2_admission_status.py
             ::_EXPECTED + BACKEND_ROUTES.md §DURABLE-ADMISSION STATUS birlikte güncellenir.
  · P8-B3b — JOBS_AND_EVENTS.md gövdesindeki ~30 `:NN` → sembol adı.
             Her referansı TEK TEK doğrula; toplu sed YAPMA.
  · P11-6b — a11y tab-sırası sondası Tab'a hiç basmıyor.
  · P11-8  — Lighthouse bağlı değil.
  · P10-7  — latency ratio gate (5 gecelik baseline gerekiyor).
  AGENT İŞİ DEĞİL: P11-1 (branch protection — repo ayarı), üç blocker, A-08 kapatma.

ÇEKİRDEK İLKE (ADIM 41'den devralınan, pazarlıksız)
  Bir tutarsızlık gördüğünde SIRAYLA sor:
    1) AYIRT EDİCİ ÖLÇÜM — iki taraf gerçekten aynı şeyi mi yapıyor?
       (Kümeyi TÜRET, elle sayma: bkz. _admission_commands.)
    2) KANONİK — UÇ UÇ sor, sayfa sayfa değil. MTR literal wire contract taşıyabilir.
    3) Kanonik konuşuyorsa HİZALA; SESSİZSE UYDURMA → adjudication kaydı + PO.
  Sevk edilmiş desen bir OLGU'dur, kanonik bir kural DEĞİL.

TAVİZ VERİLEMEZ
  · OCC token'ları, Idempotency-Key davranışı, route YOLLARI, react-query key'leri DEĞİŞMEZ.
  · Hata zarfı tek şekildir (O-02): shared/responses.py::ErrorBody.
  · Yeni gövde yayımlarken `dict[str, Any]` BIRAKMA; alan-düşmezliği SAKLANAN zarfa karşı
    kanıtla (hand-written key set kendi kendini doğrular, bir şey kanıtlamaz).
  · Kapı eklersen NEGATİFİNİ kanıtla (kapıyı kıran değişiklik + koşu çıktısı).
  · Yeşile zorlama YOK: kapı kırmızıysa BLOCKED yaz.
  · Blocker sayısı DEĞİŞMEZ; verdict BLOCKED KALIR. "READY" YAZMA.
  · Docs PR'ı EN YÜKSEK RİSKLİ tiptir (repoda ÜÇ KEZ kayıt sildi):
      git diff origin/main -- docs/ | grep '^-## '   → BOŞ OLMALI
  · CLAUDE.md §Current position 5–6 satır kalır — slice anlatısı PROJECT_HISTORY.md'ye.

KAPANIŞ
  · CLAUDE.md §Session CLOSING ritüelinin 6 maddesi.
  · cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
  · cd backend && uv run python -m entropia.apps.api.openapi_export --check
  · cd backend && TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/<worktree>_test uv run pytest
```
