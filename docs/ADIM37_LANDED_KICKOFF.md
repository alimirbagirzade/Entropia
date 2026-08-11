<!-- doc-status: historical -->
> **SUPERSEDED — canlı devir belgesi `docs/ADIM38_LANDED_KICKOFF.md`'dir.**
> Bu belge **ADIM 37 kapanışında** yazıldı ve o anın kaydıdır. Aşağıdaki *paste-ready
> resume prompt* artık **kullanılmamalıdır**: ADIM 38 landed olduğu için sıradaki iş
> P11-2'dir (ADIM 39) ve tohumu ADIM 38 kickoff'unun altındadır. P10-B2'nin **PO kararı
> bekleyen** yarısı hâlâ açıktır; kaydı burada ve raporun §6.7.5'inde durur.

# ADIM 37 LANDED — RC §6.7 / P10-B2: sayfalama sınırının şemada yayımlanması

**Base:** `origin/main` = `881d273` (#658) · **Branch:** `fix/rc-p10b2-pagination-limit-contract`
· **Tarih:** 2026-08-11 · Migration **yok** · `ENGINE_VERSION` **sabit** ·
`SHARED_ALLOCATION_STATUS` = `future_dev` · `frontend/src` **hiç dokunulmadı**.

---

## 0. ÖNCE BUNU OKU — numaralandırma düzeltmesi

Bu slice'ın kickoff prompt'u kendisini **"ADIM 36"** diye adlandırıyordu. **ADIM 36
doludur:** RC §6.7 / P6-ek + P6-6 harness fail-fast slice'ı (PR **#658**, merge commit
`881d273`, `docs/ADIM36_LANDED_KICKOFF.md`, rapor §6.7.4). CLAUDE.md merge edilmiş bir
numarayı yeniden atamayı yasakladığı için bu slice **ADIM 37**'dir.

Aynı sebeple yeni bulgu **P10-B6**'dır — `P10-B1`..`P10-B5` doludur.

**Ders:** kickoff prompt'undaki numara da handoff gibi **BAYAT-VARSAYILANDIR**. Yeni bir
slice açarken `grep -rn "ADIM <n>" docs/` ile numaranın boş olduğunu doğrula.

---

## 1. Ne landed

**(1) YAYIMLAMA — yapıldı.** Dokuz kelepçeli `limit` parametresinin hiçbiri sınırını
bildirmiyordu; artık dokuzu da default + tavan bildiriyor.

**(2) AŞIM DAVRANIŞI — bilerek YAPILMADI.** Sessiz clamp mi 422 red mi olacağı bir ürün
kararıdır, canonical sessizdir → adjudication olarak kaydedildi, **PO kararı bekliyor**.

### Reuse anchor'ları (tam sembol adlarıyla)

| Sembol / dosya | Ne yapar |
|---|---|
| **`backend/src/entropia/apps/api/pagination.py::clamped_limit_query`** | **YENİ.** Kelepçeli bir `limit` query parametresi üretir: `description` + `x-clamp-default` + `x-clamp-maximum`. `le=`/`ge=` **EMİTLEMEZ**. |
| `backend/tests/contract/test_pagination_limit_contract.py` | **YENİ.** 5 test + `CLAMPING_ENDPOINTS` tablosu (yayımlanan ↔ uygulanan drift guard'ı). |
| `backend/tests/contract/test_pagination_limit_contract.py::_json_schema_maximum` | `anyOf` dalındaki `maximum`'u da okur — opsiyonel parametrelerde sığ kontrol sahte kırmızı verir. |
| `domain/agent_lab/cursor.py::clamp_limit` (20/100) · `queries/log_projection.py::_clamp_limit` (**50**/100) · `queries/panel_backtest_log.py::_clamp_limit` (**25**/100) | Üç kelepçe, **üç farklı default**. Değişmediler. |
| `docs/CODEMAPS/BACKEND_ROUTES.md` §SAYFALAMA SINIRI | İki ailenin haritası + "yeni uç eklerken" kuralı. |

### Ölçülen sonuç

```
limit params total: 28
  ENFORCED  (JSON Schema maximum -> 422): 19
  CLAMPED   (x-clamp-maximum     -> 200):  9
  UNPUBLISHED:                             0
  clamped params ALSO emitting `maximum`:  0
```

**Negatif kanıt:** tek uç geri alındı → `exit 1`, üç test kırmızı, uç **adıyla**
raporlandı (`['/api/v1/view-datasets']`). Geri yüklendi.

---

## 2. Bu slice'ın bıraktığı KURALLAR (kopyalama, bunlardan geçir)

1. **Yeni bir liste ucu eklerken `limit`'i sınırsız bırakma.** Aşımı **reddediyorsa**
   `le=<max>` yaz (JSON Schema `maximum` doğru olur). **Kelepçeliyorsa**
   `clamped_limit_query(default=..., maximum=...)`'dan geçir ve sabitleri **kendi sorgu
   katmanının uyguladığı** değerlerden ver. Kapı aksi halde kırar.
2. **Kelepçeli bir parametre ASLA `maximum` emitlemez.** O keyword "bundan büyükler
   geçersiz" der; bu uçlar onları kabul ediyor. Emitlemek eksik sözleşmeyi **yanlış**
   sözleşmeyle değiştirir — üretilmiş istemci, sunucunun 200 döndüğü isteği reddeder.
3. **`x-clamp-*` bu repodaki İLK `x-` uzantısıdır** (öncesinde 0 taneydi). Tek bir yerde
   tanımlı, kapı pinliyor. Standart-dışıdır ve bu **bilinçli takastır**: yanlış bir
   standart alan yerine doğru bir standart-dışı alan.
4. **Opsiyonel parametrelerde şema sınırı `anyOf`'un İÇİNDEDİR.** Yalnız üst seviyeye
   bakan bir tarama `manual/search`, `manual/stream`, `trash-entries`'i sahte "yayımlamıyor"
   gösterir. Bu tuzağa bir kez düşüldü ve testin içine yazılarak kapatıldı.

---

## 3. AÇIK KALAN — bir sonraki oturumun bilmesi gerekenler

### 3.1 P10-B2 (2) — **PO kararı bekliyor. Agent bunu kendi başına KAPATAMAZ.**

Canonical (MTR §2.1 satır 11800, MTR §8 satır 12032–12044, doc 19 satır 513/923/1197/10688,
doc 18, doc 22) cursor pagination'ı ve `meta.pagination` alanlarını zorunlu kılar ama
**ne MAX_LIMIT değerini ne aşım kuralını** bildirir. İki okuma, gerekçeleri ve
**bağlayıcı olmayan** komşu sinyal (MTR 7560/7605 position sizing: *"clamp değil blocker"*)
rapor §6.7.5'te ve
`docs/releases/evidence/2026-08-11/p10b2_pagination_limit_contract.md` §4'te kayıtlı.

**(B) 422 red seçilirse atlanmaması gereken iki şey:**
* **Zarf (O-02).** FastAPI'nin varsayılan `{"detail": [...]}` şekli adjudicated zarf
  DEĞİLDİR. `le=` taşıyan 19 uç zaten `apps/api/errors.py` handler'ından geçiyor →
  yeni 422'ler muhtemelen doğru zarfa düşer, **ama varsayma, ölç.**
* **Pin kırılacak.** `test_publishing_the_ceiling_did_not_change_the_over_limit_behaviour`
  bilerek oradadır: kararın bir refactor yan etkisi olarak sessizce yutulmasını engeller.
  Kırıldığında **kararı kaydet**, testi sustur**ma**.

### 3.2 P10-B6 — YENİ, ölçüldü, düzeltilmedi

Dört uç **etkin** sayfa boyutunu yanıtta yankılamıyor: `/agent-tasks`, `/lab/messages`,
`/hypotheses` (`next_cursor` var, `limit` yok) ve `/agent-tasks/{task_id}/tool-calls`
(**hiç metadata yok** — ne cursor, ne has_more, ne limit; 9 uç içinde **gerçekten sessiz
olan tek uç budur**).

MTR §8 `Response meta.pagination` ister; **ama** sevk edilen `meta: {cursor, has_more,
limit}` şekli MTR §8'in `{limit, next_cursor, previous_cursor, total_estimate}` şeklinden
**zaten** ad ekseninde ayrı → bu dört uçtan **büyük ve daha eski** bir sapma. Düzeltmek
yanıt gövdesini, yani **wire contract**'ı değiştirir (`lib/*.ts` + typed
`AgentToolCallListResponse`) → ayrı karar, ayrı PR.

### 3.3 §6.7'nin kalanı (bu slice'a girmedi)

P11-2/3/6/8 · P10-7 · P1-B1/B2 · P8-B1/B2/B3 · P1-Gate3 · yeni P10-B6.
**P11-1 (branch protection) AGENT İŞİ DEĞİL** — repo ayarı, insan kararı.
**Dört blocker DEĞİŞMEDİ; §8 verdict BLOCKED KALIR.**

---

## 4. Çalışma yöntemi — bu koşuda işe yarayan

- **İddiayı önce yeniden üret.** Rapor "9 uç" dedi → doğruydu; "hepsi aynı desen" ve
  "sessizce" dedi → **ikisi de yanlıştı**. Sayıyı doğrulamak nitelemeyi doğrulamaz.
- **İki soruyu fiziksel olarak ayır.** "Yayımla" ile "davranışı değiştir" FastAPI'de
  `le=` üzerinden **birleşiktir**; ayrı tutmak için `le=` yerine `x-` uzantısı gerekti.
  Bu ayrımı görmeden `le=100` eklemek, (2)'yi farkında olmadan karara bağlardı.
- **Frontend'i ÖLÇ, varsayma.** `lib/*.ts` bu 9 uca hiç `limit` göndermiyor → ileride red
  seçilse bile repo içi kırılan çağıran **0**. Bu ölçüm kararın maliyetini değiştirir.
- **Kapının negatifini kanıtla.** Yeşil bir kapı, kapı olduğunun kanıtı değildir.
- **Ölçüm tuzakları:** `pytest`i `| tail`'e borulama (exit code `tail`'in olur) · alt küme
  koşarken `--no-cov` ekle · `TEST_DATABASE_URL` ile worktree'ye özel izole DB
  (`postgresql+asyncpg://`) · suite koşarken `uv run`/`uv sync` çalıştırma ·
  docs PR'ı öncesi `git diff origin/main -- docs/ | grep '^-## '` **boş** olmalı.

---

## 5. PASTE-READY RESUME PROMPT

```
ENTROPIA V18 — ADIM 38: [SLICE ADI]

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — ADIM 37 / P10-B2 merged olmalı; `git fetch` + `gh pr list`)
Branch: [branch adı]

ÖNCE DOĞRULA (handoff BAYATTIR, prompt'taki NUMARA da bayat olabilir)
  · `git fetch && git log --oneline origin/main -6 && gh pr list --state all`
  · `grep -rn "ADIM 38" docs/` → BOŞ olmalı; doluysa bir sonraki boş numarayı al.
    (ADIM 36 iki kez talep edildi; ADIM 37 bu yüzden doğdu.)
  · ADIM 37 gerçekten indi mi? `docs/openapi.json` içinde `x-clamp-maximum` **9 kez**
    geçmeli; `backend/tests/contract/test_pagination_limit_contract.py` var olmalı.

ADIM 37'NİN BIRAKTIKLARI (kopyalama, bunlardan geçir)
  · `apps/api/pagination.py::clamped_limit_query` — kelepçeli `limit` yayımlayan TEK yer.
    Yeni liste ucu: aşımı REDDEDİYORSA `le=<max>`, KELEPÇELİYORSA bu declarator.
    Sınırsız bırakılan `limit` `tests/contract/test_pagination_limit_contract.py`'de kırılır.
  · Kelepçeli parametre ASLA `maximum` emitlemez (yanlış red vaadi olur).
  · Opsiyonel parametrede şema sınırı `anyOf`'un İÇİNDE — sığ tarama sahte kırmızı verir.

AÇIK VE AGENT'IN KAPATAMAYACAĞI
  · **P10-B2 (2) — aşım davranışı: PO kararı bekliyor.** Canonical sessiz. Sessiz clamp mi
    422 red mi — KENDİ BAŞINA SEÇME. Kayıt: rapor §6.7.5 +
    `docs/releases/evidence/2026-08-11/p10b2_pagination_limit_contract.md` §4.
    (B) seçilirse: zarf O-02'den geçmeli, ve
    `test_publishing_the_ceiling_did_not_change_the_over_limit_behaviour` pin'i kırılacak —
    kararı KAYDET, testi susturma.
  · **P10-B6 (yeni, ölçüldü, düzeltilmedi):** 4 uç etkin sayfa boyutunu yankılamıyor;
    `/agent-tasks/{task_id}/tool-calls` hiç metadata döndürmüyor. Düzeltmek WIRE CONTRACT
    değiştirir (`lib/*.ts` + typed `AgentToolCallListResponse`) → ayrı karar, ayrı PR.
  · **P11-1 (branch protection) AGENT İŞİ DEĞİL** — repo ayarı, insan kararı.
  · **Dört blocker DEĞİŞMEDİ. Verdict BLOCKED KALIR. "READY" YAZMA.**

ÖLÇÜM TUZAKLARI (bu repoda gerçekten yaşandı)
  · pytest'i | tail'e BORULAMA — exit code tail'in olur.
  · Alt küme koşarken --no-cov EKLE (yoksa %90 kapısı sahte kırmızı).
  · vitest: --no-file-parallelism ZORUNLU; `frontend/node_modules` yoksa önce `npm ci`.
  · TEST_DATABASE_URL ile worktree'ye özel izole DB; sürücü postgresql+asyncpg://
  · Suite koşarken `uv run`/`uv sync` çalıştırma; tam suite TEK çağrıda, ortada öldürme.
  · ci.yml: job'ın GERÇEKTEN koştuğunu job log'undan doğrula.
  · docs PR'ı öncesi: git diff origin/main -- docs/ | grep '^-## ' → BOŞ olmalı.

KAPANIŞ
  · CLAUDE.md §Session CLOSING ritüelinin 6 maddesi (handoff · kickoff+resume ·
    PROJECT_HISTORY tam kayıt + CLAUDE.md 5–6 satır özet · ecc graph + claude-mem ·
    codemap · commit→PR→merge bekle).
  · Ham çıktılar → docs/releases/evidence/<YYYY-MM-DD>/
  · cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```

---

## 6. Kapanış ritüelinde EKSİK KALAN (dürüst sınır)

**claude-mem checkpoint'i YAZILAMADI.** MCP sunucusu bu oturumda **worker** modunda koştu:
`observation_add` / `memory_add` `CLAUDE_MEM_RUNTIME=server-beta` istiyor ve transport hata
döndürdü; worker modunda yalnız `search` / `timeline` / `get_observations` çalışıyor.
Ayrıca oturum başında Claude Desktop OAuth token'ının bayat olduğu bildirildi.

**ecc knowledge graph checkpoint'i YAZILDI** — entity
`Entropia ADIM 37 — RC 6.7 / P10-B2: pagination limit published in the schema`
(20 gözlem) + `unblocks` ilişkisi. Ritüelin 4. maddesinin **yarısı eksiktir**; bir sonraki
oturum `mem-search` ile bu slice'ı **bulamayabilir** — `PROJECT_HISTORY.md` §ADIM 37 ve bu
belge otoritedir. Eksik kapatılmadı, **kaydedildi**.
