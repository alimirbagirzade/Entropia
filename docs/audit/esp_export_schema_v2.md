<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# ESP Export Contract — schema v2 (G-02)

> Kanonik kaynak: doc 09 §15 **ESP-19**, doc 09 §14, doc 08 §7 "Export" / §9.1 `package_export` / §10 Import.
> Kapatılan boşluk: `docs/audit/current_main_ground_truth_2026-08-03.md` **§G-02**.
> Base: `origin/main` @ `6c46c03`. **Migration YOK** — alembic head `0043_i08_registry_strategy_fks` değişmedi.
> **`ENGINE_VERSION` DEĞİŞMEDİ**: backtest motoru, indikatör matematiği ve sayısal semantik bu
> slice'ta hiç dokunulmadı; değişen yüzey yalnız export artifact'inin şekli ve import'un okuma kuralıdır.

---

## 1. Neden

Doc 09 ESP-19 aynen şunu ister: *"Artifact contains root/revision identity, content hash,
signature, adapter ref, evidence and dependency manifest."*

Schema v1 bu cümlenin yalnız **identity + content hash + dependency manifest** yarısını
taşıyordu. `runtime_adapter`, `warm_up_period`, `timing_semantics`, `repaint` ve
test-vector evidence'ı `embedded_resolver_contract`'ta; validation run kanıtı
`embedded_resolver_validation_run`'da yaşıyor — manifest ise yalnız `package_revision`'dan
kuruluyordu. Sonuç: **dışa aktarılmış bir ESP, hangi runtime/timing semantiğiyle
doğrulandığını söyleyemiyordu**; artifact tek başına yeniden üretilebilir değildi.

Kusur, kod yazılmadan önce `origin/main` @ `6c46c03` üzerinde geçici bir probe testiyle
empirik olarak yeniden üretildi (contract ve validation-run satırları veritabanında
**mevcutken** manifest dört alanın dördünü birden atlıyordu). Probe ağaçta bırakılmadı —
kalıcı karşılığı `test_esp_export_contract_v2.py::test_esp_export_v2_carries_contract_adapter_and_validation_evidence`'tır;
slice revert edilirse o test **kırmızıya döner**, yani regresyon kapısı orada.

---

## 2. v1 ↔ v2 uyumluluk matrisi

| Alan | v1 | v2 | Import v1 okur mu | Import v2 okur mu | Not |
|---|---|---|---|---|---|
| `export_schema_version` | **yok** | `2` | — | ✔ | Alanın yokluğu = v1 (alan bu artifact'lardan sonra doğdu) |
| `exporter_version` | yok | `"entropia-package-exporter-v2"` | — | ✔ (bilgi) | Şekli değil, **üreteni** adlandırır |
| `package_root_id` · `revision_id` · `revision_no` | ✔ | ✔ (aynı) | ✔ | ✔ | |
| `package_kind` · `name` | ✔ | ✔ (aynı) | ✔ | ✔ | `_coerce_kind` NOT NULL kapısı |
| `input_contract` · `output_contract` | ✔ | ✔ (aynı) | ✔ | ✔ | |
| `dependency_snapshot` | ✔ | ✔ (aynı) | ✔ | ✔ | Import **daima** yerelde yeniden çözer |
| `rationale_family_snapshot` | ✔ | ✔ (aynı) | ✔ | ✔ | |
| `validation_state` · `approval_state` | ✔ | ✔ (aynı) | ✔ | ✔ | |
| `content_hash` · `derived_from_revision_id` | ✔ | ✔ (aynı) | ✔ | ✔ | |
| `resolver_contract_snapshot` | **yok** | ✔ / `null` | — | ✔ (yalnız **untrusted echo**) | ESP değilse `null` |
| `validation_evidence_snapshot` | **yok** | ✔ / `null` | — | ✔ (yalnız **untrusted echo**) | Contract yoksa `null` |
| `registry_observation` | yok | **manifest'te DEĞİL** — zarfın kardeşi | — | — | Yabancı sisteme hiç seyahat etmez |

### Versiyon kabul kuralı (`resolve_import_schema_version`)

| Gelen `export_schema_version` | Sonuç |
|---|---|
| alan yok | `1` — kabul (eski artifact) |
| `null` (açık) | `1` — kabul. JSON `null` **değerin yokluğudur**, bilinmeyen bir gelecek versiyon değil; alan-yok ile aynı okunur |
| `1` · `2` (int) | kabul |
| `"1"` · `"2"` (digit string) | kabul (elle yapıştırılan manifest toleransı) |
| `3`, `99`, `0`, `-1`, `"next"`, `"2.0"`, `""`, `true`, `[2]`, `{...}` | **RED** |

`true` bilerek listede: naif bir `raw in {1, 2}` kontrolü Python'da `True == 1` olduğu için
onu kabul ederdi ve `export_schema_version: true` olan bir manifest v1 artifact **değildir**.

**Red iki katmanda, fail-closed:**
1. API sınırı — `commands/package_import.py::_coerce_schema_version` → **422
   `PACKAGE_IMPORT_MANIFEST_INVALID`**, durable job açılmadan önce.
2. Worker — `jobs/package_import.py::_manifest_defect` → terminal `failed`
   (`reason: unsupported_export_schema_version`), paket yaratılmaz.

> **Hata kodu kararı (kanonik boşluk).** Doc 08 §11 taksonomisi okunamayan bir şema versiyonu
> için **kod adlandırmıyor**. Kanonik boşlukta ürün kararı uydurulmaz; bu yüzden yeni bir kod
> icat edilmedi, sevk edilmiş `PACKAGE_IMPORT_MANIFEST_INVALID` yeniden kullanıldı — sınıfın
> kendi tanımı zaten "structurally unusable at the API boundary" diyor, okunamayan versiyon
> tam olarak budur.

### Hash uyumluluğu (dürüst sınır)

Aynı revision'ın v1 ve v2 artifact'i **farklı `manifest_hash` üretir** — alan kümesi
farklıdır, bu kaçınılmazdır. Bu bir bozulma değil, versiyonlamanın sebebidir:
`export_schema_version` okuyucuya hangi şekli elinde tuttuğunu söyler ve **hash'ler
versiyonlar arasında asla karşılaştırılmaz**. Kayıtlı v1 hash'leri geçerli kalır; onları
üreten audit satırları ve `package_import_job.manifest_hash` değerleri dokunulmadı.

### Pre-G-02 Idempotency-Key replay'i

G-02 öncesi yazılmış bir replay kaydı dört anahtarlı zarf taşır. `_with_export_envelope_defaults`
**kopya üzerinde** `export_schema_version: 1` ve `registry_observation: null` doldurur; saklı
`response_ref` JSON'u mutate EDİLMEZ ve **manifest verbatim döner** — içine versiyon alanı
geri-doldurmak, audit'in çoktan kaydettiği `manifest_hash`'i geçersiz kılardı. (O-30'da purge
202 için kurulan kalıbın aynısı.)

---

## 3. v2 şeması

### `resolver_contract_snapshot` (ESP revision'ları; aksi hâlde `null`)

| Alan | Kaynak | Not |
|---|---|---|
| `contract_id` | `embedded_resolver_contract.contract_id` | |
| `package_root_id` · `revision_id` | aynı satır | **Export edilen** revision, kökün head'i değil |
| `canonical_key` | aynı satır | ESP-19 "signature" yüzeyinin kimliği |
| `signature` | aynı satır (JSONB) | |
| `runtime_adapter` | aynı satır | ESP-19 **"adapter ref"** |
| `warm_up_period` · `timing_semantics` · `repaint` | aynı satır | Adapter'ı yorumlanabilir kılan timing semantiği |
| `evidence` | aynı satır (JSONB) | ESP-19 **"evidence"** — test-vector'lar |

`created_at` **bilerek yok**: satır-doğum damgasıdır, contract olgusu değildir ve doc 09 §15
onu istemez. Hash'e girseydi determinizm iddiası yeniden-seed edilmiş bir ortamda çökerdi.

### `validation_evidence_snapshot` (contract varsa; aksi hâlde `null`)

| Alan | `recorded` | `legacy_incomplete_evidence` |
|---|---|---|
| `evidence_state` | `"recorded"` | `"legacy_incomplete_evidence"` |
| `validation_run_id` | run satırı | `null` |
| `validator_version` | run satırı (`esp-validation-v1`) | `null` |
| `status` | run satırı (`passed`/`warning`/`failed`) | **`null`** |
| `vectors_run` · `checks` | run satırı | `null` |
| `completed_at` | run satırı, ISO-8601 | `null` |
| `revision_validation_state` · `revision_approval_state` | **her zaman** revision'ın kendi durumu | **her zaman** revision'ın kendi durumu |

**Kritik kural:** revision `passed` okuyup hiç run satırı olmayabilir (R8 öncesi legacy
aktivasyon). Bu durumda `evidence_state = legacy_incomplete_evidence` ve `status = null`
kalır; revision'ın kendi `passed` durumu **ayrı bir alanda, kendi adıyla** raporlanır.
Artifact, doğrulayıcı-sertifikalı kanıt olarak sunmadığı bir şeyi asla `passed` diye
reklam etmez (doc 09 §7).

### `registry_observation` (zarf — manifest'in İÇİNDE DEĞİL)

`canonical_key` · `trust_state` · `trusted_active_revision_id` · `registry_version` ·
`runtime_adapter` · `is_trusted_active_revision`.

Canlı ESP registry pointer'ı, export edilen revision'dan **bağımsız** hareket eder. Manifest'in
içinde olsaydı, registry her kımıldadığında aynı revision'ın yeniden export'u farklı hash
verirdi — ve "eski revision canlı registry'den yeniden yorumlanmaz" kuralı yalan olurdu.
Zarfta durması ayrıca **yabancı sisteme hiç seyahat etmemesini** sağlar: import daima yerel
registry'de yeniden çözer.

---

## 4. Determinizm — ne garanti edilir, ne edilmez

> Bu bölüm 2026-08-03'te bir adversarial review'dan sonra **daraltıldı**. İlk yazımı
> "aynı immutable girdi → aynı hash, **her zaman**" diyordu; iki geçici probe testi bunun
> **yanlış** olduğunu gösterdi ve iddia gerçeğe hizalandı. Aşağıdaki her satır ölçülmüştür.

### 4.1 Garanti EDİLEN

**İddia.** Arada hiçbir şey değişmediyse yeniden export digest'i **birebir** üretir.

**Neden.**
1. Kurucu düzlemde **hiçbir yerde `now()` okunmaz** (`domain/package/export_contract.py` saf,
   I/O'suz) — export-zamanı damgası hash'e giremez.
2. `embedded_resolver_contract` gerçekten immutable'dır (`revision_id` üzerinde UNIQUE, onu
   mutate eden bir yazıcı yok) ve `created_at` **bilerek taşınmaz** — satır-doğum olgusudur,
   contract olgusu değil; doc 09 §15 onu istemez.
3. Canlı registry state'i hash'in **dışındadır** — manifest'in kardeşi `registry_observation`.
4. `get_latest_validation_run` sıralaması **total**dir (`created_at DESC, run_id DESC`).
   `created_at` = `func.now()` = *transaction* timestamp olduğu için tek tx'te insert edilen
   iki run tam olarak eşitlenir; tiebreaker olmadan seçim planlayıcıya kalırdı — yani
   content-addressed bir manifest'in içinde yazı-tura. `run_id` (`new_id`: sabit genişlikli
   base32 zaman damgası + rastgele) benzersiz ve leksikografik sıralanabilir.
5. `manifest_hash` = `sha256(canonical_json(manifest))` — `shared/hashing.py`'deki tek
   kanonikleştirici (`sort_keys=True`), elle `json.dumps` yok.

### 4.2 Garanti EDİLMEYEN (dürüst sınır)

Manifest'in taşıdığı **iki olgu gerçekten mutable'dır**. Aynı revision'ın sonraki export'u
bu iki eksende **farklı bir artifact**'tır — ve doğrusu budur; artifact hangisi olduğunu
kendisi söyler:

| Hareket | Etki | Neden doğru davranış bu |
|---|---|---|
| Revision yeniden validate edilir (`run_resolver_validation` yeni bir run satırı ekler) | `validation_evidence_snapshot` **en yeni** run'ı izler → yeni `validation_run_id`, yeni hash | `run_resolver_validation` en yeni run'ın status'unu `revision.validation_state`'e kopyalar. Daha eski bir run'ı pinlemek, sistemin artık `failed` saydığı bir revision'a `passed` reklamı yaptırırdı — **tam da bu slice'ın engellemek için var olduğu kusur**. `validation_run_id` hangi kanıtın bu digest'i desteklediğini adlandırır; artifact asla belirsiz değildir |
| Revision approve edilir / activate edilir | `approval_state` (ve evidence snapshot'ındaki `revision_approval_state`) değişir → yeni hash | Bu kolonlar `package_revision` üzerinde **yerinde** güncellenir (`commands/esp.py:280,366`, `commands/package_lifecycle.py:534,716`). Alanı atmak artifact'i "bu revision hiç approve edildi mi" sorusuna sağır bırakırdı; digest'i "revision ömrü boyunca dondu" diye ilan etmek ise düpedüz yalan olurdu |

**Doğru cümle:** artifact, *bir revision'ın export anındaki sertifikalı durumunun*
content-addressed anlık görüntüsüdür — export-zamanı saatinden ve canlı registry'den
bağımsız, ama revision'ın kendi lifecycle ilerleyişinden bağımsız **değil**.

### 4.3 Kanıtlayan testler

`backend/tests/integration/test_esp_export_contract_v2.py`:

| Test | Kanıt |
|---|---|
| `test_same_immutable_input_hashes_identically_across_separate_exports` | **Farklı** idempotency key'lerle iki bağımsız export → aynı manifest, aynı hash; artifact'tan hash yeniden hesaplanır (kendini doğrular). v2 alanlarının hash preimage'ında olduğu **önce** assert edilir — aksi hâlde test slice revert edilse de geçerdi (v1 de iki ardışık çağrıda deterministikti) ve hiçbir şeyi korumazdı |
| `test_registry_moves_but_the_immutable_artifact_does_not` | `ta.sma` deprecate edilir; `manifest_hash` **aynı**, `registry_observation` değişir |
| `test_old_revision_export_is_not_reinterpreted_through_the_current_head` | Head ileri alınır; ESKİ revision'ın yeniden export'u aynı hash. Contract taşımayan yeni head `null` döner — selefinin contract'ını ödünç almaz |
| `test_a_second_validation_run_produces_a_new_artifact_that_names_its_run` | §4.2 satır 1: hash **değişir**, `validation_run_id` **değişir** ve seçilen run repo'nun total sıralamasının döndürdüğü run'dır |
| `test_an_approval_transition_produces_a_new_artifact_of_the_same_revision` | §4.2 satır 2: `draft → approved` hash'i hareket ettirir; iki alan da (manifest + evidence snapshot) birlikte hareket eder |
| `test_the_hash_preimage_covers_the_contract_and_evidence_but_not_live_registry` | Hash **sınırı**: contract + evidence içeride (sahte adapter / sahte `passed` yakalanır), `registry_observation` dışarıda |

> **Tamper hakkında dürüst sınır.** Yukarıdaki doğrulama, digest'in **bağımsız bir
> kopyasını elinde tutan dış okuyucuya** açıktır. Sistem, **gönderilen** bir `manifest_hash`'i
> asla yeniden doğrulamaz — `submit_package_import` kendi digest'ini hesaplar ve hiçbir şeyle
> karşılaştırmaz. Bu bilinçlidir: import, gelen hash'e güvenmek yerine **yerelde yeniden
> çözer** (§5). "Tamper detection" bir sistem davranışı değil, artifact'in okuyucuya sunduğu
> bir özelliktir.

## 5. Trust sınırı (import)

| Kural | Nerede zorlanır |
|---|---|
| Manifest'in `runtime_adapter` iddiası **yerel güven yaratmaz** | `jobs/package_import.py::_reresolve` yalnız yerel `TRUSTED_ACTIVE` + `PASSED` + `APPROVED` çözer; manifest'in adapter'ı hiç okunmaz |
| Import **`embedded_resolver_contract` satırı yazmaz** | `test_v2_origin_contract_is_echoed_as_untrusted_and_grants_no_local_trust` (satır sayımı) |
| Import **`embedded_resolver_registry` pointer'ı yazmaz** | aynı test |
| Yabancı iddia raporda görünür ama **reddiyle birlikte** | `diagnostics.origin_resolver_contract` → `trusted: false`, `local_revalidation_required: true` |
| Import edilen paket **asla çalıştırılabilir değildir** | `validation_state=pending`, `approval_state=draft`; çözülemeyen bağımlılık → `blocked` + `failed` validation |

**Round-trip kanıtı:** `test_real_exported_esp_artifact_round_trips_without_minting_trust` —
gerçekten trusted bir ESP export edilir, ürettiği **tam artifact** geri import edilir; kanıtı
`passed` olmasına rağmen sonuç DRAFT/PENDING paket, sıfır yeni contract satırı, sıfır yeni
registry satırı. Bir dosyayı import etmek trusted resolver basmanın yolu değildir.

---

## 6. Değişen yüzeyler

| Katman | Dosya | Değişiklik |
|---|---|---|
| Domain (yeni) | `backend/src/entropia/domain/package/export_contract.py` | Saf kurucu düzlem + versiyon kuralı |
| Command | `application/commands/package_lifecycle.py` | `export_package` v2; `_with_export_envelope_defaults` |
| Command | `application/commands/package_import.py` | `_coerce_schema_version` kapısı (kind'dan ÖNCE) |
| Job | `application/jobs/package_import.py` | Versiyon defence-in-depth + untrusted origin echo |
| Route | `apps/api/routes/library.py` | `PackageExportResponse` — gövde artık şemada yayımlı |
| OpenAPI | `docs/openapi.json` | 1 yeni schema, 1 operation body ref; **operation sayısı değişmedi** |
| Frontend | `lib/library.ts`, `pages/Library.tsx` | `RegistryObservation` wire tipi; şema versiyonu satırı + ayrı observation bloğu |

**DEĞİŞMEYENLER:** route path'leri, react-query key'leri, OCC token'ları, `Idempotency-Key`
üretimi, SSE taksonomisi, `app/nav.ts`, DB şeması, `ENGINE_VERSION`, non-ESP export'un v1
gövdesi (yalnız iki versiyon alanı + iki `null` eklenir).
