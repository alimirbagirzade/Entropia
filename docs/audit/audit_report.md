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
