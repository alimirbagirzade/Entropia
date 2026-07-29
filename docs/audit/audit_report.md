# Entropia — Spec-vs-Code Audit Report

Her bölüm bir spec dokümanının **kod karşılığını** ampirik olarak denetler: önce kanıt
(grep / dosya+satır / test koşusu), sonra düzeltme. Bir madde "var" diye işaretlendiyse
altında onu kanıtlayan dosya:satır referansı bulunur; "yok" diye işaretlendiyse düzeltmenin
landed olduğu dosya ve testi bulunur.

---

## Doc 19 — Panel / Management / Logs (`docs/spec/19_Entropia_V18_Panel_Management_Logs_Page_Documentation_v1_1.md`)

**Denetim tarihi:** 2026-07-29 · **Branch:** `feat/audit-doc19-panel-verification`
**Kapsam:** doc 19'un tamamı (1292 satır) okundu; §4.2 Role Assignment commandi, §4.3 event
modeli, §5 interaction state matrix, §6.1/§6.2 field contract, §7.1 UI metinleri, §8
Button-Command tablosu, §11 Validation/Error/Recovery tablosu ve §14 acceptance testleri
koda karşı doğrulandı.

**Sonuç: doc 19 TEMİZ DEĞİL — 2 bulgu.** Beş denetim sorusundan üçü tam çıktı, biri kısmi,
biri eksikti. İkisi de bu branch'te düzeltildi.

### Denetim matrisi

| # | Denetim sorusu | Ampirik sonuç | Durum |
|---|---|---|---|
| 1 | `LAST_ADMIN_PROTECTION` / `AGENT_ROLE_NOT_ASSIGNABLE` / `USER_ROLE_VERSION_CONFLICT` kodları var mı? | 3'ten **2'si** vardı | **BULGU-1 → düzeltildi** |
| 2 | No-op role save `changed=false` kararı uygulanıyor mu? | Backend yarısı vardı, **UI yarısı yoktu** | **BULGU-2 → düzeltildi** |
| 3 | Logs filtre yüzeyi tam mı (family/severity/actor_type/resource_type/correlation_id/from/to/q)? | **8/8 tam** (+`actor_id`, `cursor`, `limit`) | Temiz |
| 4 | "Source is deleted. See Trash." deleted-subject durumu var mı? | **Var** (backend + UI) | Temiz |
| 5 | Correlation chain görünümü var mı? | **Var** (chain + causation, backend + UI) | Temiz |

---

### BULGU-1 — `LAST_ADMIN_PROTECTION` kodu hiç emit edilmiyordu (doc 19 §7.1, §9.3, §11, §14)

**Kanıt (düzeltme öncesi, denetimin kendi komutu):**

```
$ grep -rn "LAST_ADMIN_PROTECTION\|AGENT_ROLE_NOT_ASSIGNABLE\|USER_ROLE_VERSION_CONFLICT" backend/src
backend/src/entropia/shared/errors.py:173:    code = "AGENT_ROLE_NOT_ASSIGNABLE"
backend/src/entropia/shared/errors.py:199:    code = "USER_ROLE_VERSION_CONFLICT"
```

`LAST_ADMIN_PROTECTION` **sıfır** sonuç verdi. Son Admin'i düşürme yolu
(`application/commands/role_assignment.py` → `domain/identity/policy.py::ensure_not_last_admin`)
`LastAdminProtectedError` fırlatıyordu; wire kodu `LAST_ADMIN_PROTECTED`.

**Neden gerçek bir kusur:** doc 19 bu kodu dört ayrı yerde `LAST_ADMIN_PROTECTION` diye
adlandırıyor (§7.1 "Last Admin blocker" satırı, §9.3 akışı, §11 Validation tablosu, §14
acceptance testi) ve doc 19'un kaynak modülü olan Master **Modül 16** de aynı yazımı
kullanıyor (`Master_Technical_Reference_v1_0.md:10590, :10806, :10836`). Kodda sevk edilen
`LAST_ADMIN_PROTECTED` ise Master **Modül 3**'ün yazımı (`:1414, :1490, :1506`) — yani
legacy `PATCH /users/{id}/role` deactivation yüzeyinin taksonomisi. Doc 19'un belgelenmiş
koduna dallanan bir client (veya Agent) Panel'de bu kodu **hiç göremiyordu**; §7.1'in
"Assign another Admin first" blocker metni yerine generic handler'a düşüyordu.

**Adjudication — iki isim, iki yüzey (K-07 şekli):** İsimlerden biri "yanlış" değil; ikisi
de spec'te, farklı sayfa taksonomilerinde. Repo'da bunun yerleşik kararı var: upload
dosya-tipi kapısı tek kusuru beş sayfa koduna ayırıyor ("her sayfanın kendi §-taksonomisi
otoritedir"). Aynı şekil uygulandı:

- Legacy Modül 3 yüzeyi (`commands/roles.py`) → `LAST_ADMIN_PROTECTED` **aynen kaldı**.
- Doc 19 Panel yüzeyi (`commands/role_assignment.py`) → `LAST_ADMIN_PROTECTION`.
- **Tek kapı korundu:** `ensure_not_last_admin` hâlâ tek sayma-ve-blokla kuralı; yüzey kodu
  çağrı yerinde `error=` ile bağlanıyor, kural kopyalanmıyor.
- Yeni sınıf `LastAdminProtectedError`'ın **alt sınıfı** → hangi yüzeyin fırlattığını
  umursamayan çağıranlar `except LastAdminProtectedError` yazmaya devam ediyor (mevcut
  4 test dosyası değişmeden geçti).

**Landed:**

| Dosya | Değişiklik |
|---|---|
| `backend/src/entropia/shared/errors.py:170` | Yeni `LastAdminProtectionError(LastAdminProtectedError)`; `code="LAST_ADMIN_PROTECTION"`, 422, `retryable=False`, §7.1 mesajı, `suggested_action="assign_another_admin"`, `remediation`, `scope_type="human_user"`, `field_path="target_role"` (O-02 recovery zarfı) |
| `backend/src/entropia/domain/identity/policy.py:150` | `ensure_not_last_admin(..., error=LastAdminProtectedError)` — varsayılanlı, tek kapı korunur |
| `backend/src/entropia/application/commands/role_assignment.py:119` | Panel çağrısı `error=LastAdminProtectionError` geçer |

**Kanıt (düzeltme sonrası):**

```
$ grep -rn "LAST_ADMIN_PROTECTION\|AGENT_ROLE_NOT_ASSIGNABLE\|USER_ROLE_VERSION_CONFLICT" backend/src
backend/src/entropia/shared/errors.py:188:    code = "LAST_ADMIN_PROTECTION"
backend/src/entropia/shared/errors.py:199:    code = "AGENT_ROLE_NOT_ASSIGNABLE"
backend/src/entropia/shared/errors.py:225:    code = "USER_ROLE_VERSION_CONFLICT"
```

**Yeni testler:**

- `backend/tests/integration/test_panel_management_logs.py::test_last_admin_protection_emits_doc19_taxonomy_code`
  — gerçek DB'de tek Admin'i Supervisor yapmaya çalışır; `code == "LAST_ADMIN_PROTECTION"`,
  `http_status == 422`, `retryable is False`, §7.1 mesajının birebir metni ve
  `field_path == "target_role"` doğrulanır; ayrıca `current_role`/`version` değişmediği ve
  `audit_events` + `outbox_events` sayısının artmadığı (§11 "no mutation / no audit event")
  kanıtlanır.
- `…::test_last_admin_protection_clears_once_a_second_admin_exists` — blocker'ın kalıcı kilit
  değil canlı sayım olduğunu kanıtlar: §7.1'in söylediği remedy (başka bir Admin ata)
  uygulanınca aynı demote başarıyla commit olur.
- `backend/tests/unit/test_identity_policy.py::test_last_admin_gate_binds_the_callers_surface_error_code`
  — tek kapının iki yüzey kodunu da ürettiğini, varsayılan (Modül 3) bağlamanın bozulmadığını
  ve alt-sınıf ilişkisinin korunduğunu pinler.

---

### BULGU-2 — No-op role save'in UI yarısı sevk edilmemişti (doc 19 §4.2 Implementation Decision, §7.1)

**Kanıt (backend yarısı — VARDI):** `application/commands/role_assignment.py:97-101` seçilen
role mevcut role eşitse version bump'ı, audit event'i ve outbox'ı **atlıyor** ve projeksiyonu
`changed=False` ile döndürüyor; `test_panel_management_logs.py:164` bunu zaten pinliyordu.
Bu yarı temizdi.

**Kanıt (UI yarısı — YOKTU):** doc 19 §4.2'nin Implementation Decision kutusu tek karar
değil, iki yarımdır: "API current user projectionını `changed=false` ile döndürür; **UI 'No
role change was needed.' bilgisini gösterir**." §7.1 ayrıca "Role success" metnini de birebir
tanımlar. Sevk edilen UI (`frontend/src/pages/PanelManagement.tsx:138-142`) iki sonucu tek
satırda birleştiriyordu:

```
Role assignment accepted — alice → supervisor (v4, unchanged).
```

Bu, hiçbir şey olmadığı durumu ("unchanged" eki) olan-ama-log'a-henüz-düşmemiş durumdan
ayırmıyordu — §4.2'nin bu kararı almasının nedeni tam olarak buydu.

**Landed:** `frontend/src/pages/PanelManagement.tsx` — §7.1'in iki metni birebir:

- `changed=true` → `Role updated. {username} is now {role}. The audit event will appear in Logs shortly.`
- `changed=false` → `No role change was needed.`

Presentation-only: route path, react-query key, OCC token (`expected_head_revision_id`),
`Idempotency-Key` ve `lib/adminPanel.ts` veri yolu **dokunulmadı**.

**Testler:** `frontend/src/test/panelManagement.test.tsx` — mevcut role-assign testinin metin
iddiası yeni markup'a hizalandı (OCC gövdesi `{target_role, expected_head_revision_id: 3}`,
`Idempotency-Key` ve option listesi iddiaları **değişmedi**); yeni
`it("reports a no-op role save as 'No role change was needed.' …")` bloğu `changed:false`
yanıtını stub'layıp §7.1 metnini ve "Logs shortly" metninin **görünmediğini** pinler.

---

### Temiz çıkan maddeler (kanıtlı)

**#3 — Logs filtre yüzeyi tam.** doc 19 §6.2'nin dokuz query alanının tamamı server-side
uygulanıyor:

| §6.2 alanı | Route | Query katmanı |
|---|---|---|
| `from` / `to` | `admin_panel.py:150-151` (+ `from > to` → 422, `:165`) | `log_projection.py:86-89` |
| `family` | `admin_panel.py:152` | `log_projection.py:90-91` + `_family_predicate` (ilk-eşleşme sırası `event_family` ile birebir) |
| `severity` | `admin_panel.py:153` | `log_projection.py:92-93` |
| `actor_type` / `actor_id` | `admin_panel.py:154-155` | `log_projection.py:94-97` |
| `resource_type` | `admin_panel.py:156` | `log_projection.py:98-99`; opsiyonlar `GET /admin/log-resource-types` ile audit satırlarından hidrate (§6.2 "dynamically derived") |
| `correlation_id` | `admin_panel.py:157` | `log_projection.py:100-102` — exact-or-prefix, 64 char cap, raw wildcard yok |
| `q` | `admin_panel.py:158` | `log_projection.py:103-111` — trim + 128 char cap, yalnız indeksli alanlar (`event_kind`, `target_entity_id`, `reason`), raw payload aranmıyor |
| `limit` / `cursor` | `admin_panel.py:159-160` | default 50 / max 100 (`log_projection.py:36-46`), opaque composite keyset cursor (`:115-131`) |

Client-side filtre yok; tarayıcıya tam geçmiş yüklenmiyor (§13).

**#4 — Deleted-subject durumu var.** `log_projection.py:222-231` (`_subject_status`)
`EntityRegistry.deletion_state` üzerinden subject'in lifecycle'ını çözer; detail
`subject_status` + `subject_deleted` taşır (`:269`). Event **silinmez**, retained kalır (§11).
UI karşılığı: `frontend/src/pages/PanelLogs.tsx:430` → `Source is deleted. See Trash.` +
Admin-only `/trash` linki (§5 "Deleted source reference", §7.1).

**#5 — Correlation chain var.** `log_projection.py:246-254` aynı `correlation_id`'li
event'leri zaman sırasıyla (200 cap) döndürür; `:256-260` `causation_event_id`'yi ayrı satır
olarak çözer (§4.3 "View correlation chain" + causation row). UI:
`frontend/src/pages/PanelLogs.tsx:439-445` sayılı disclosure. Drawer read-only —
edit/delete/retry/rerun kontrolü yok, `PATCH`/`DELETE` route'u da yok (§11 audit integrity,
§13).

**Ek olarak doğrulanan (denetim sorusu değildi, §11/§8 taraması sırasında):**
`AGENT_ROLE_NOT_ASSIGNABLE` 422 olarak hem enum kapısında (`policy.py:143-147`) hem Agent
principal hedefinde (`role_assignment.py:83-86`) fırlıyor; `USER_ROLE_VERSION_CONFLICT` 409,
`category=concurrency_or_preflight`, `retryable=true`; `require_admin_panel` her endpoint'te
**ve** her command/query içinde ayrıca uygulanıyor (§2 Derived Rule); dual-token uzlaştırması
`reconcile_occ_tokens` üzerinden (O-12).

---

### Doğrulama koşuları

```
# Denetimin istediği kontrol adımı — yeşil
$ uv run pytest -k "panel_management or panel_logs" -q --no-cov
26 passed        # 24 baseline + 2 yeni entegrasyon testi

# Genişletilmiş yüzey (roles / identity / admin / error taxonomy / legacy upgrade)
$ uv run pytest -k "panel or identity or role or admin or error_taxonomy or error_envelope \
                    or legacy_upgrade or stage1_persistence or log_resource" -q --no-cov
205 passed

# Tam backend suite (worktree'ye özel izole DB, tek koşu)
$ uv run pytest --no-cov -q
2609 passed / 0 failed

$ uv run ruff check .            # All checks passed!
$ uv run ruff format --check .   # 667 files already formatted
$ uv run mypy src                # Success: no issues found in 371 source files

$ npx vitest run --no-file-parallelism src/test/panelManagement.test.tsx src/test/panelLogs.test.tsx
2 files / 21 tests passed        # 20 baseline + 1 yeni no-op testi
```

**Migration yok** (alembic head değişmedi), **ENGINE_VERSION bump yok** — bu slice yalnız
hata taksonomisi ve sunum katmanına dokunur.

### Dürüst sınırlar

- Bu bölüm doc 19'un **backend + frontend kod karşılığını** denetler; V18 mockup'a karşı
  piksel/görsel kıyas yapılmadı.
- §5'in loading/skeleton state metinleri ile §7.1'in kalan bilgi-metni kataloğu (ⓘ popover
  içerikleri) satır satır kıyaslanmadı — doc 19 §7 bunları "Productionda ⓘ eklenirse
  kullanılacak" içerik sözleşmesi sayıyor, zorunlu render değil.
- Otorite CI'dır; yukarıdaki koşular worktree'ye özel izole DB üzerinde alınmıştır.

---

## Doc 22 — Future Dev: "statik placeholder yanlışlıkla aktif iş yapıyor mu?"

- **Denetim tarihi:** 2026-07-29 · **Branch:** `feat/audit-doc22-future-dev-verification`
- **Spec:** `docs/spec/22_Entropia_V18_Future_Dev_Page_Documentation_v1_1.md` (tamamı, 1295 satır)
- **Kapsam:** Capability Registry, placeholder yüzeyi, activation gate'leri, Graphic View,
  Agent tool sınırı — doc 22 §3, §4, §4.1, §4.2, §5, §7, §8, §9, §9.1, §9.2, §11, §12, §16
- **Otoriteler:** CR-08 (Admin-only lifecycle transition), CR-09 (inactive capability
  gerçek job/dataset/order/authoritative output üretemez), FD-01…FD-15
- **Sonuç:** **CR-09 fail-closed DOĞRULANDI.** Placeholder bir capability hiçbir job,
  dataset, artifact veya outbox event üretemiyor. §7 metin katalogunda **3 sapma**
  bulundu ve düzeltildi; 3 bilinçli sapma kayda geçirildi.

### Denetlenen yüzey (koddan sayıldı)

| Katman | Dosya | Rol |
|---|---|---|
| Domain | `backend/src/entropia/domain/capability/baseline.py` | 7 slot PLACEHOLDER seed + §4.1/§7 verbatim copy + `UI_SURFACE_VERSION_V18` |
| Domain | `backend/src/entropia/domain/capability/lifecycle.py` | state graph (`:40` PLACEHOLDER→DESIGNED), gate contract, `ensure_operational` |
| Domain | `backend/src/entropia/domain/agent_lab/tool_gateway.py` | `CAPABILITY_GATED_TOOLS` + `exposed_tool_names` (CR-08) |
| Application | `backend/src/entropia/application/commands/capability.py` | transition + 2 operasyonel komut (`:313`, `:402` state kapısı) |
| Application | `backend/src/entropia/application/queries/capability.py` | registry projeksiyonları + Graphic View overview |
| Application | `backend/src/entropia/application/jobs/agent_tools.py` | `:568`/`:591` Agent tool handler'ları |
| API | `backend/src/entropia/apps/api/routes/capability.py` | 9 endpoint (aşağıda) |
| Frontend | `frontend/src/pages/FutureDev{,Capability,GraphicView}.tsx` | 3 sayfa (registry + 6 alt sayfa + Graphic View) |
| Frontend | `frontend/src/app/{nav.ts,Layout.tsx}` | Future Dev mavi dropdown + pasif "Live Trade" leaf |

Yayımlanan Future Dev API yüzeyi (`docs/openapi.json`) — **9 path, Live Trade order
endpoint'i YOK** (FD-12):

```
GET  /api/v1/capabilities
GET  /api/v1/capabilities/{capability_key}
GET  /api/v1/capabilities/{capability_key}/lifecycle-transitions
POST /api/v1/capabilities/{capability_key}/lifecycle-transitions   (Admin-only)
GET  /api/v1/future-dev/graphic-view/overview
POST /api/v1/view-datasets/query                                   (graphic_view Limited/Active)
GET  /api/v1/view-datasets  ·  GET /api/v1/view-datasets/{id}
POST /api/v1/analysis-artifacts                                    (tipe göre gating capability)
GET  /api/v1/analysis-artifacts  ·  GET /api/v1/analysis-artifacts/{id}
```

---

### Soru 1 — Placeholder capability gerçekten hiçbir job/dataset üretemiyor mu? CR-09 kapısı her giriş noktasında var mı?

**Cevap: EVET, fail-closed. Sapma yok.**

Kalıcı Future Dev çıktısı yazabilen **tam olarak iki** kod yolu var
(`grep create_view_dataset|create_analysis_artifact` → repository dışında başka
çağıran yok):

| Yazma yolu | Giriş noktaları | CR-09 kapısı |
|---|---|---|
| `capability_repo.create_view_dataset` | `commands/capability.py::query_view_dataset` | `require_operational_capability(session, GRAPHIC_VIEW)` — `_op()` içinde, **validation'dan ÖNCE** (`capability.py:313`) |
| `capability_repo.create_analysis_artifact` | `commands/capability.py::create_analysis_artifact` | `require_operational_capability(session, gating_capability)` (`capability.py:402`) |

Her iki komutun **iki** çağıranı var ve ikisi de aynı komuttan geçiyor — ayrı bir
"arka kapı" yok:

1. **HTTP:** `routes/capability.py:133` ve `:151`
2. **Agent tool:** `jobs/agent_tools.py:575` (`view_dataset.query`) ve `:597`
   (`analysis_artifact.create`)

Kapı `domain/capability/lifecycle.py::ensure_operational` → `OPERATIONAL_STATES`
(= `{LIMITED, ACTIVE}`) dışındaki her state'te `CapabilityNotActiveError`.
Placeholder, Designed, Internal, Shadow **ve Retired** hepsi reddediliyor (FD-11).

**İkinci savunma hattı (CR-08):** `exposed_tool_names` (`tool_gateway.py:128`),
`agent_loop.py:86-87`'de canlı registry'den okunan `operational_capability_keys()`
ile çağrılıyor — Placeholder/Designed capability'nin tool'u Agent'ın plan adımına
**hiç sunulmuyor** (FD-10). Yine de tool zorla çağrılırsa komut katmanı reddediyor
ve bu **kayıtlı bir REJECTED denial** oluyor (doc 22 §12 "Agent records blocker").

**Kalıcı kayıt sızıntısı yok:** `run_idempotent` idempotency satırını `_op()`'tan
önce ekliyor, ama `_op()` fırlattığında istisna `TransactionBoundaryMiddleware`'e
kadar çıkıyor ve `deps.py:51/77` `session.rollback()` yapıyor — reddedilen çağrıdan
geriye **hiçbir satır** kalmıyor. Bu ampirik olarak doğrulandı (aşağıdaki kontrol adımı).

**Modellenmemiş olması doğru olanlar:** `experiment_proposal` ve `execution_plan`
entity'leri hiç yok — doc 22 §9 zaten "Future-only; no ... action in Placeholder" ve
"Does not exist as active V1 live trading domain" diyor. Gate'lenecek bir yazma yolu
olmadığı için yokluk doğru davranış.

---

### Soru 2 — Graphic View placeholder'ı sahte veri render ediyor mu?

**Cevap: HAYIR. Sapma yok.**

`FutureDevGraphicView.tsx` hiçbir seri, fiyat, metrik veya eğri üretmiyor. Sayfadaki
tüm içerik `GET /future-dev/graphic-view/overview` sunucu projeksiyonundan geliyor
(`queries/capability.py::get_graphic_view_overview`) ve o query de sadece
`GRAPHIC_VIEW_INTRO` + 6 statik kart + registry state döndürüyor. Chart canvas,
timer, mock progress, `localStorage` kalıcılığı veya rastgele değer yok — doc 22
§4.2 "Async progress: No job exists in Placeholder state. Timer veya mock progress
yasaktır" karşılanıyor.

Altı kartın metni de **gelecek zamanlı** (`"Future: …"`), yani doc 22 §6 "Card wording
operation varmış izlenimi vermemeli" kuralına uyuyor — bu artık test ile pinlendi.

Operasyonel View Dataset formu **sadece** sunucunun `is_operational === true` demesi
hâlinde render ediliyor (`FutureDevGraphicView.tsx:55,98`) ve bilinmeyen state
(loading/error) **fail-closed** gizliyor. Bu bir sunum kararı; sunucu her dispatch'te
state'i yeniden kontrol ediyor.

---

### Soru 3 — doc 22 §4.1/§7 verbatim metinleri UI'da doğru mu?

**§4.1 (Graphic View placeholder sayfası): 7/7 DOĞRU.** Intro + altı kartın başlık ve
metni `baseline.py`'de birebir; sıraları da doc sırasıyla aynı.

**§7 (Information Content Catalog): 10 anahtarın 7'si doğruydu, 3'ü sapmıştı → düzeltildi.**

| §7 anahtarı | Denetim öncesi | Aksiyon |
|---|---|---|
| `futureDevOverview.placeholder` | ✅ verbatim | — |
| `futureDevOverview.designed` | ✅ verbatim | — |
| `futureDevOverview.limited` | ✅ verbatim | — |
| `futureDevGraphicView.placeholder` | ✅ verbatim | — |
| `futureDevDisabled.tooltip` | ❌ **hiç yoktu** | **FIX 3** |
| `CAPABILITY_NOT_ACTIVE` | ❌ `"This capability is not active."` | **FIX 1** |
| `CAPABILITY_DEPENDENCY_MISSING` | ✅ verbatim | — |
| `CAPABILITY_STATE_STALE` | ❌ `"… Refresh capability status."` (kesik) | **FIX 2** |
| `CAPABILITY_ACCESS_DENIED` | ✅ verbatim | — |
| `futureDevNoHistory.empty` | ✅ verbatim (frontend) | — |

#### FIX 1 — `CAPABILITY_NOT_ACTIVE` mesajı (en ciddi bulgu)

`shared/errors.py:148` sınıfı `message = "This capability is not active."` taşıyordu.
Bu metin doc 22 §7'deki **başka bir anahtarın başlık sütunundan** (`futureDevOverview.placeholder`
Başlık = "This capability is not active") geliyordu; §7'nin `CAPABILITY_NOT_ACTIVE`
için tanımladığı **Nihai UI metni** ise:

> This feature is not active in the current environment. **No operation was started.**

Kaybedilen ikinci cümle tam olarak bu denetimin konusu: çağırana *hiçbir işin
başlamadığını* söyleyen tek cümle, yani CR-09 sözünün kullanıcıya bakan yarısı.
Kod fail-closed davranıyordu ama **onu söylemiyordu**. Düzeltildi.

#### FIX 2 — `CAPABILITY_STATE_STALE` mesajı

`"… Refresh capability status."` → doc §7 verbatim `"… Refresh capability status before
continuing."` ("before continuing" = doc §12 "do not retry blindly" davranışının metni).

#### FIX 3 — `futureDevDisabled.tooltip` eksikti

Doc §7 bu metni "Disabled/non-operational button or item" için zorunlu kılıyor. V18'de
tek böyle öğe var: Future Dev dropdown'undaki pasif **Live Trade** leaf'i
(`nav.ts:233` — hedefi yok, doc §4 "onclick/clickable tanımı yok"). `Layout.tsx`'te
`<span className="item" aria-disabled="true">` olarak render ediliyordu, açıklama
taşımıyordu. Artık doc §7 metnini `title` olarak taşıyor.

**Kapsam disiplini:** `nav.ts` NAV/`MENU_BAR` verisine dokunulmadı; değişiklik sadece
`Layout.tsx`'in leaf render dalında ve tamamen sunum katmanında. Route path'leri,
react-query key'leri, OCC token'ları ve Idempotency-Key davranışı değişmedi.

#### Kayda geçirilen, düzeltilmeyen sapmalar (bilinçli)

- **§5 recovery metinleri literal olarak yok.** doc §5 Interaction State Matrix'in
  "Recovery / kullanıcı mesajı" sütunundaki iki cümle (`"Live Trade is not active in
  Production V1. No execution action is available."` ve `"Graphic View is a controlled
  placeholder. No visual dataset has been prepared."`) kodda birebir geçmiyor. Yerlerini
  §7 kataloğunun daha genel metinleri tutuyor (`futureDevDisabled.tooltip` artık Live
  Trade'de; Graphic View'da `STATE_MESSAGES[PLACEHOLDER]` + `GRAPHIC_VIEW_INTRO`).
  §7 "Bu metinler doğrudan UIya yerleştirilebilir" diyerek katalogu otorite sayıyor;
  aynı anlamı iki farklı cümleyle iki yerde tutmak drift kaynağı olurdu. **Açık kalem.**
- **Guest görünürlüğü kapalı.** doc §3'ün Implementation Decision'ı public placeholder
  overview'ların Guest tarafından read-only görülebilmesini seçiyor; sevk edilen
  `get_graphic_view_overview` ise `require_authenticated` istiyor. Bu, auth remediation
  dalgasının (#346–#364) bilinçli sıkılaştırması ve doc §3'ün kendi kaçış maddesiyle
  ("Deploymentte public navigation kapatılırsa route da aynı policy ile kapatılmalıdır")
  uyumlu. **Gevşetilmedi** — bir güvenlik denetiminin kararını doc uyumu adına geri
  almak yanlış olurdu. **Kayıtlı sapma.**
- **Overview path'i `graphic-view`, doc'ta `graphic_view`.** doc §8 `GET /api/v1/future-dev/
  graphic_view/overview` yazıyor (capability_key'i path'e koyarak). Sevk edilen path
  `/api/v1/future-dev/graphic-view/overview` — kebab-case API konvansiyonu. Path zaten
  `docs/openapi.json`'da yayımlanmış ve frontend'e bağlı; değiştirmek sunum-dışı bir
  kırılma olurdu. **Kayıtlı sapma.**

---

### Soru 4 — `UI_SURFACE_VERSION_V18 = "v18-placeholder"` tüketiliyor mu?

**Cevap: EVET — kalıcı, sunuluyor ve tipli. Ama hiçbir ekranda RENDER edilmiyor.**

Tüketim zinciri (hepsi koddan doğrulandı):

1. **Seed:** `alembic/versions/0020_future_dev.py:24,226` — 7 baseline satırın hepsi
   bu değerle yazılıyor.
2. **Repository default:** `repositories/capability.py:147,157` — yeni `create_capability`
   çağrıları da aynı değeri alıyor.
3. **Persistence:** `models/capability.py:65` `String(32) NOT NULL`.
4. **API çıktısı:** `queries/capability.py:56` (`GET /capabilities`, `GET /capabilities/{key}`)
   ve `commands/capability.py:163` (transition yanıt zarfı).
5. **Client tipi:** `frontend/src/lib/capability.ts:27,78` — `Capability` ve
   `CapabilityDetail` tiplerinde `ui_surface_version: string`.

Yani doc 22 §9'un `future_capability.ui_surface_version` alanı **ölü sabit değil**:
her registry satırının hangi UI yüzeyine karşı tasarlandığını taşıyor ve API'den
dönüyor. Hiçbir `.tsx` dosyası onu ekrana basmıyor — **doc 22 bunu zaten talep
etmiyor** (§6'da "UIda gizli system identifier" sınıfındaki alanlarla aynı kategoride,
§4.1'de Graphic View için "V18de explicit badge yok" deniyor). Sapma değil; dürüst
sınır olarak kaydediliyor.

---

### Uygulanan değişiklikler

| # | Dosya | Değişiklik |
|---|---|---|
| FIX 1 | `backend/src/entropia/shared/errors.py` | `CapabilityNotActiveError.message` → doc §7 verbatim (`"… No operation was started."`) |
| FIX 2 | `backend/src/entropia/shared/errors.py` | `CapabilityStateStaleError.message` → doc §7 verbatim (`"… before continuing."`) |
| FIX 3 | `frontend/src/app/Layout.tsx` | pasif placeholder leaf'i doc §7 `futureDevDisabled.tooltip` metnini `title` olarak taşıyor |
| GUARD | `backend/tests/unit/test_doc22_copy_fidelity.py` (yeni) | §4.1 intro + 6 kart + §5/§7 state mesajları + 4 hata metni/kodu + `UI_SURFACE_VERSION_V18` verbatim pinleniyor |
| GUARD | `backend/tests/integration/test_doc22_placeholder_no_job.py` (yeni) | **HTTP seviyesinde** CR-09 kanıtı: iki operasyonel POST → 403 `CAPABILITY_NOT_ACTIVE`, `jobs` sayısı sabit, 0 satır |
| GUARD | `frontend/src/test/futureDevDisabledTooltip.test.tsx` (yeni) | Live Trade leaf'i `<span aria-disabled>`, link/button değil, tooltip verbatim |

`code`, `http_status`, `category`, `retryable`, `details`, tablo/kolon şeması, route
path'leri, react-query key'leri, OCC ve Idempotency-Key davranışı **değişmedi**;
migration eklenmedi (alembic head `0039_backtest_run_cancellation` aynı kaldı).

Not: `CapabilityNotActiveError` bir `ForbiddenError` ve `category` bildirmiyor
(O-02'de "sınıflandırılmamış hata asla `retryable=true` reklamı yapmaz" — ampirik
olarak `retryable=false` döndüğü doğrulandı). Doc 22 bu alan için bir kategori
tanımlamadığından bilerek dokunulmadı.

---

### Kontrol adımı (tekrar üretilebilir)

```bash
cd backend && TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_audit_doc22" \
  LC_ALL=en_US.UTF-8 uv run pytest -k "capability or future_dev or doc22" -q --no-cov
```

Sonuçlar (2026-07-29, bu worktree, izole DB):

| Gate | Sonuç |
|---|---|
| `pytest -k "capability or future_dev or doc22"` | **143 passed / 0 failed** |
| `pytest -k "openapi or error_envelope"` (drift guard) | **16 passed** |
| `ruff check .` · `ruff format --check .` | temiz · 672 dosya |
| `mypy src` | 371 dosyada sorun yok |
| `npx vitest run --no-file-parallelism` | **643 passed / 62 dosya** |
| `npx tsc --noEmit` · `npx eslint src --max-warnings=0` | temiz · temiz |

**Ampirik CR-09 kanıtı** (`test_doc22_placeholder_no_job.py`, HTTP yüzeyi üzerinden,
`graphic_view` state'i `placeholder` iken):

```
POST /api/v1/view-datasets/query      → 403  CAPABILITY_NOT_ACTIVE, retryable=false
POST /api/v1/analysis-artifacts       → 403  CAPABILITY_NOT_ACTIVE, retryable=false
GET  /api/v1/future-dev/graphic-view/overview → 200, is_operational=false, 6 statik kart

SELECT count(*) FROM jobs                → ARTMADI (before == after)
SELECT count(*) FROM view_dataset        → 0
SELECT count(*) FROM analysis_artifact   → 0
SELECT count(*) FROM outbox_event        → 0
```

**Sonuç: doc 22 CR-09 fail-closed doğrulandı.** Placeholder yüzeyi aktif iş yapmıyor;
bulunan üç sapma metin katmanındaydı (davranış değil) ve düzeltildi.
