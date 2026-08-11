<!-- doc-status: current -->

# P10-B2 — sayfalama sınırının şemada yayımlanması (ADIM 37)

**Tarih:** 2026-08-11 · **Branch:** `fix/rc-p10b2-pagination-limit-contract` ·
**Base:** `origin/main` = `881d273` (ADIM 35 / PR #659 merged — doğrulandı)

> **Bu belge iki ayrı şeyi kaydeder ve onları KARIŞTIRMAZ:**
> **(1) YAYIMLAMA** — sevk edilen davranışın görünür kılınması. **YAPILDI.**
> **(2) AŞIM DAVRANIŞI** — sessiz clamp mı, 422 red mi. **ÜRÜN KARARI, YAPILMADI.**
> §4'te adjudication olarak kayıtlı, PO kararı bekliyor.

---

## 0. Numaralandırma düzeltmesi (önce bunu oku)

Bu slice'ın kickoff prompt'u kendisini "ADIM 36" diye adlandırıyordu. **ADIM 36 doludur:**
RC §6.7 / P6-ek + P6-6 harness fail-fast slice'ı (PR #658, merged `881d273`,
`docs/ADIM36_LANDED_KICKOFF.md`). CLAUDE.md'nin kuralı merge edilmiş numarayı yeniden
atamayı yasakladığı için bu slice **ADIM 37** olarak kaydedildi.

Aynı sebeple yeni bulgu **P10-B6**'dır: `P10-B1`..`P10-B5` doludur
(`P10-B3` = Alertmanager delivery proof, `P10-B5` = on-call rotasyonu).

---

## 1. Raporun iddiası — yeniden doğrulandı, biri düzeltildi

Rapor (§6.7, satır 853) şöyle diyordu:

> 9 uçta sayfalama sınırı **şemada yayımlanmıyor** → `limit=100000` reddedilmiyor,
> sessizce 100'e iniyor.

**Sayı DOĞRU: tam 9 parametre.** Adıyla, ve her biri hangi kelepçeyi uyguluyor:

| # | Uç | Kelepçe fonksiyonu | default | tavan |
|---|---|---|---|---|
| 1 | `GET /api/v1/admin/users` | `domain/agent_lab/cursor.py::clamp_limit` | 20 | 100 |
| 2 | `GET /api/v1/admin/backtest-logs` | `queries/panel_backtest_log.py::_clamp_limit` | **25** | 100 |
| 3 | `GET /api/v1/admin/logs` | `queries/log_projection.py::_clamp_limit` | **50** | 100 |
| 4 | `GET /api/v1/agent-tasks` | `clamp_limit` | 20 | 100 |
| 5 | `GET /api/v1/agent-tasks/{task_id}/tool-calls` | `clamp_limit` | 20 | 100 |
| 6 | `GET /api/v1/lab/messages` | `clamp_limit` | 20 | 100 |
| 7 | `GET /api/v1/hypotheses` | `clamp_limit` | 20 | 100 |
| 8 | `GET /api/v1/view-datasets` | `clamp_limit` | 20 | 100 |
| 9 | `GET /api/v1/analysis-artifacts` | `clamp_limit` | 20 | 100 |

**"Hepsi aynı deseni mi kullanıyor?" — HAYIR, ve rapor bunu bildirmemişti.**
Üç ayrı kelepçe fonksiyonu var ve **default'ları AYNI DEĞİL** (20 / 25 / 50). Tavan
üçünde de 100. Yayımlama bu yüzden tek bir sabiti değil, **her ucun kendi ikilisini**
taşımak zorundaydı — yoksa yayımlanan sayı uygulanandan sapardı.

Bir ölçüm tuzağı da burada yakalandı: `manual/search`, `manual/stream` ve
`trash-entries` uçları ilk taramada "yayımlamıyor" göründü. **Yanlıştı** — bu üçü
`int | None` + `le=100` taşıyor ve FastAPI bir OPSİYONEL parametrenin sınırını
`anyOf` dalının İÇİNE koyuyor. Yalnız üst seviyeye bakan bir kontrol onları sahte
kırmızıya çevirir. Test bunu `_json_schema_maximum` içinde açıkça ele alıyor.

---

## 2. Teşhis — clamp gerçekten "sessiz" mi? ÖLÇÜLDÜ

Prompt'un sorusu: bu 9 uç yanıtında sayfalama METADATA'sı dönüyor mu? Cevap **tek
değil, ÜÇ katmanlı** — ve bu, bulgunun ağırlığını raporun yazdığından farklı kılıyor.

| Katman | Uçlar | Dönen metadata | İstemci kesildiğini anlar mı? |
|---|---|---|---|
| **A — tam gözlenebilir** | `/admin/users`, `/admin/backtest-logs`, `/admin/logs`, `/view-datasets`, `/analysis-artifacts` (5) | `meta: {cursor, has_more, limit}` — **`limit` ETKİN (kelepçelenmiş) değeri yankılar** | **EVET, doğrudan.** `limit=100000` gönderen istemci `meta.limit=100` okur. |
| **B — kısmen** | `/agent-tasks`, `/lab/messages`, `/hypotheses` (3) | `{<items>, next_cursor}` — `has_more` **hesaplanıyor ama dönmüyor**, etkin limit yankılanmıyor | **Kısmen.** `next_cursor != null` "daha var" der; ama limitinin indirildiğini söylemez. |
| **C — gerçekten sessiz** | `/agent-tasks/{task_id}/tool-calls` (1) | `{tool_calls}` — cursor yok, has_more yok, limit yok | **HAYIR.** 100000 ister, 100 alır, **hiçbir sinyal yok.** |

**Sonuç:** raporun "sessizce 100'e iniyor" ifadesi **9 uç için değil, 1 uç için**
tam doğrudur (katman C); 3 uçta kısmen; 5 uçta **yanlıştır** — orada clamp zaten
runtime'da makine-okunabilir biçimde bildiriliyordu.

Bu, bulgunun ağırlığını **azaltmaz, yerini değiştirir**: asıl kusur "istemci
kesildiğini anlayamıyor" değil, **"istemci sınırı ÖNCEDEN öğrenemiyor"** idi.
Sözleşmeyi okuyup istek kuran bir istemci (kod üreteci dahil) 9 ucun HİÇBİRİNDE ne
default'u ne tavanı bulabiliyordu. Bu slice tam olarak onu kapatır.

Katman B ve C'nin runtime yankı boşluğu **ayrı bir kusurdur, ÖLÇÜLDÜ ve
DÜZELTİLMEDİ** → **P10-B6** (§5).

---

## 3. Ne yapıldı — yayımlama (1)

Yeni ortak declarator: **`backend/src/entropia/apps/api/pagination.py::clamped_limit_query`**.
Dokuz parametrenin dokuzu da bundan geçiyor. Yayımladığı:

* `description` — insan metni: default, tavan, ve **aşımın RED DEĞİL KELEPÇE olduğu**.
* `x-clamp-default` / `x-clamp-maximum` — makine-okunabilir sayılar.

**Bilerek yayımlanmayan: JSON Schema `maximum`.** Gerekçe adjudicated değil, mantıksal:
`maximum` "bundan büyük değerler GEÇERSİZ" demektir ve bu sunucu onları **kabul ediyor**.
Onu emitlemek, eksik bir sözleşmeyi **yanlış** bir sözleşmeyle değiştirirdi — üretilmiş
bir istemci, sunucunun 200 döndüğü isteği reddederdi. `x-` uzantısı hiçbir kod
üretecinin doğrulama sınırı sanamayacağı tek biçimdir.

> **Not:** bu, repoda ilk `x-` uzantısıdır (snapshot'ta önceden **0** tane vardı).
> Yeni bir kelepçeli uç eklerken sözleşmeyi route'a kopyalama, bu fonksiyondan geçir.

### Ölçülen sonuç (`docs/openapi.json`, yeniden üretildi)

```
limit params total: 28
  ENFORCED  (JSON Schema maximum -> 422 on over-limit): 19
  CLAMPED   (x-clamp-maximum     -> 200, page shrunk):   9
  UNPUBLISHED (no ceiling at all):                       0
  clamped params that ALSO emit a (false) `maximum`:     0
```

Ham diff: `p10b2_openapi_diff.txt` (45 eklenen / 9 silinen satır).

### Davranış DEĞİŞMEDİ

`le=` / `ge=` **eklenmedi**; `default=None` korundu. Route yolları, OCC token'ları
(`If-Match` / `expected_*_version` / `X-*-Version`), `Idempotency-Key`, react-query
key'leri, dönüş gövdeleri ve `response_model`'lar **aynen** kaldı.

**Frontend etkisi ÖLÇÜLDÜ, sıfır:** `frontend/src/lib/*.ts` bu 9 uca **hiç `limit`
göndermiyor** (yalnız `lib/adminPanel.ts` `meta.limit`'i **okuyor**). >100 gönderen tek
bir çağrı bile yok, yani (2) için ileride red seçilse bile repo içi hiçbir çağıran
kırılmaz. Repo dışı çağıranlar bilinmiyor.

### Kapı ve negatif kanıtı

`backend/tests/contract/test_pagination_limit_contract.py` — 5 test:

1. hiçbir `limit` parametresi sınırsız yayımlanamaz (**asıl kapı**; yeni bir liste ucu
   sınırını bildirmezse burada kırılır, bir sonraki readiness denetiminde değil);
2. iki aile kesişmez ve 28'i tam böler (19 + 9);
3. kelepçeli bir parametre **asla** `maximum` reklamı yapmaz;
4. yayımlanan sayılar uygulanan sabitlere **eşit** (drift guard);
5. **aşım davranışı pin'i** — `clamp_limit(100_000) == 100`. İleride biri clamp'i
   red'e çevirirse bu pin kırılır ve ürün kararı bir refactor yan etkisi olarak
   sessizce yutulamaz.

**Negatif kanıt (kapı gerçekten kırmızı veriyor mu):** `capability.py`'nin TEK bir ucu
yayımlamayı bırakacak şekilde geri alındı →

```
NEGATIVE_EXIT=1
AssertionError: these `limit` parameters publish no page ceiling — ... : ['/api/v1/view-datasets']
FAILED test_every_limit_parameter_publishes_a_ceiling
FAILED test_the_two_families_partition_every_limit_parameter
FAILED test_published_bounds_equal_the_enforced_bounds
```

Uç geri yüklendi; `git diff` ile doğrulandı.

---

## 4. ADJUDICATION — aşım davranışı (2). **AÇIK. PO KARARI BEKLİYOR.**

**Bu slice bu kararı VERMEDİ ve sessiz clamp'i "böyle kalsın" diye onaylamadı.**

### 4.1 Canonical ne diyor? — **SESSİZ**

Arandı ve okundu: `docs/spec/01`..`22` + Master Technical Reference.

| Kaynak | Sayfalama hakkında ne diyor | Tavan / aşım kuralı |
|---|---|---|
| MTR §2.1 (satır 11800) | "Liste response'ları ayrıca pagination meta taşır." | **yok** |
| MTR §8 (satır 12032–12044) | Cursor pagination zorunlu; `Response meta.pagination: limit, next_cursor, previous_cursor \| null, total_estimate \| null` | **yok** |
| MTR satır 9186, 9431 | Büyük ledger/event setlerinde cursor pagination; tarayıcıya tüm datayı yükleme | **yok** |
| doc 19 §(satır 513, 923, 1197, 10688) | Admin listeleri `limit=50` + opaque cursor ister; offset yasak | **yok** — 50 bir İSTEK değeri, tavan değil |
| doc 18 | — | **yok** |
| doc 22 | — | **yok** |

**Hiçbir sayfa belgesi ne MAX_LIMIT değerini ne de aşım davranışını bildiriyor.**
Repo kuralı: *"Canonical boşlukta ürün kararı UYDURULMAZ."* → karar verilmedi.

### 4.2 İki okuma

* **(A) Sessiz clamp (BUGÜN SEVK EDİLEN).** Aşım indirilir, istek 200 döner.
  *Lehine:* istemciye affedici; kaynak tüketimi fail-safe; katman A'nın 5 ucunda
  `meta.limit` zaten etkin değeri yankılıyor, yani orada clamp gözlenebilir.
  *Aleyhine:* aynı API yüzeyinde 19 uç aynı isteğe 422 verirken bu 9'u 200 veriyor —
  tutarsız; ve katman C'de istemcinin hiçbir sinyali yok.

* **(B) 422 red (19 ucun yaptığı).** Aşım reddedilir.
  *Lehine:* tek tutarlı yüzey; yanlış istek kuran istemci bunu öğrenir.
  *Aleyhine:* davranış değişikliğidir. **Ölçüldü: repo içi hiçbir çağıran kırılmaz**
  (frontend `limit` göndermiyor); repo dışı çağıranlar bilinmiyor.

### 4.3 Bağlayıcı OLMAYAN komşu sinyal (karar niyetine değil, kayda geçirilir)

MTR **position sizing** alanında ürün, benzer şekilli bir soruyu açıkça cevaplamış:

* satır 7560: *"Base veya formula sonucu bu limiti aşarsa **clamp değil blocker** veya
  explicit cap policy uygulanır."*
* satır 7605: *"Exposure limitini aşan layer otomatik olarak 'kırpılıp' açılmaz;
  ... candidate **reddedilir** ve ledgerda reason kaydedilir."*

**Bu, sayfalama için canonical DEĞİLDİR** — farklı bir domain, farklı bir risk
(orada kırpma sahte PnL üretir, burada yalnız daha küçük bir sayfa döner). Ürünün
"sessiz kırpma" karşısındaki eğilimini gösterdiği için kayda geçirilir; karar
yerine geçmez. Bunu sayfalamaya taşımak, yasaklanan "uydurma"nın ta kendisi olurdu.

### 4.4 (B) seçilirse atlanmaması gereken tuzak — hata zarfı

FastAPI'nin VARSAYILAN doğrulama hatası `{"detail": [...]}` döner ve bu **adjudicated
zarf DEĞİLDİR**. Zarf tek şekildir (O-02): `shared/responses.py::ErrorBody` →
`code, message, details, request_id, correlation_id` + recovery bloğu
(`category, retryable, suggested_action, remediation, scope_type, scope_id, field_path`).
Bu repoda `le=` taşıyan 19 uç zaten mevcut validation exception handler'ından geçiyor
(`apps/api/errors.py`), yani (B) seçilirse yeni 422'ler **kendiliğinden** doğru zarfa
düşer — ama bunu varsaymayın, sevk ederken ölçün. Yeni bir şekil İCAT ETMEYİN.

### 4.5 Karar

**AÇIK.** Ürün sahibi (A) veya (B)'yi seçene kadar sevk edilen davranış (A)'dır ve
artık **yayımlanmıştır**, yani hiçbir istemci sınırı bilmemekten muzdarip değildir.
Kapı §3'teki 5. test ile bu durumu pinliyor: karar değiştiğinde test kırılır ve
kararın kayda geçirilmesini zorlar.

---

## 5. YENİ BULGU — P10-B6 (ölçüldü, DÜZELTİLMEDİ)

**Dört uç, uyguladığı ETKİN sayfa boyutunu yanıtta yankılamıyor** (§2, katman B ve C):
`/agent-tasks`, `/lab/messages`, `/hypotheses` (`next_cursor` var, `limit` yok) ve
`/agent-tasks/{task_id}/tool-calls` (**hiçbir sayfalama metadata'sı yok**).

Bu, MTR §8'in `Response meta.pagination` sözleşmesiyle de ayrışır. **Ancak dikkat:**
sevk edilen `meta: {cursor, has_more, limit}` şekli MTR §8'in
`{limit, next_cursor, previous_cursor, total_estimate}` şeklinden **zaten** ad
ekseninde ayrışıyor — bu, bu dört uçtan büyük ve daha eski bir sözleşme sapmasıdır.

**Neden bu PR'da düzeltilmedi:** yanıt gövdesine alan eklemek/şekil birleştirmek
**wire contract değişikliğidir**; `frontend/src/lib/*.ts` bu projeksiyonları okuyor ve
`AgentToolCallListResponse` typed bir `response_model`'dır. Bu, "sınırı yayımla"
slice'ının kapsamını aşar ve kendi kararını ister (hangi şekil kanonik olacak?).
ADIM 34'ün P4-3'te yaptığı gibi: **ölçüldü, adlandırıldı, kaydedildi.**

---

## 6. Kapsam dışı bırakılanlar (bilerek)

Dört blocker (A-08 · kabul akışları · Alertmanager · react-router freeze) ·
§6.7'nin diğer kalemleri (P11-1/2/3/6/8 · P10-7 · P1-B1/B2 · P8-B1/B2/B3 · P1-Gate3) ·
cursor tabanlı sayfalamaya geçiş · varsayılan limit değerleri (yalnız ÜST SINIR
sözleşmesi konu edildi) · `le=` taşıyan 19 ucun yeniden düzenlenmesi (onlar sınırlarını
zaten DOĞRU yayımlıyor).

**Blocker sayısı DEĞİŞMEDİ. Verdict BLOCKED KALIR.**
