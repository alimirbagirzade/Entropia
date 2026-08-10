<!-- doc-status: current -->

# RC §6.7 — P4-1 + P4-2 kapanış kanıtı (ADIM 33, 2026-08-10)

Ölçüm ortamı: yerel PostgreSQL 16 (`:5432`), `LC_ALL=en_US.UTF-8`, izole veritabanları
(`entropia_adim33`, `entropia_adim33_ca`, `entropia_adim33_mig`, `entropia_adim33_tests`).
Ham çıktılar bu dizindeki `p4_*.txt` dosyalarıdır.

## 1. Raporun iddiası yeniden ölçüldü

| İddia (§6.7) | Ölçülen | Sonuç |
|---|---|---|
| `alembic check` exit **255** | exit **255** | **DOĞRU** |
| `removed index` 39 / `added index` 39 / `changed index` 1 / `removed unique constraint` 1 | 39 / 39 / 1 / 1 | **DOĞRU** |
| **40 gerçek index-adı sapması** | 39 saf yeniden-adlandırma + 1 `agent_event.seq` çifti = **40** | **DOĞRU** |
| Hiçbir CI workflow'u `alembic check` koşmuyor | `.github/workflows/*.yml` içinde yok | **DOĞRU** |
| P4-2: `agent_event.seq`'te alembic yolunda fazladan non-unique index | `agent_event_seq_key` (UNIQUE) + `ix_agent_event_seq` (non-unique); `create_all` yolunda tek unique index | **DOĞRU** |
| P4-2 fonksiyonel etkisi yok | aşağıda deneysel kanıt | **DOĞRU** |
| *"Emitlediği farkların tamamı index/constraint eksenindedir"* / *"tip/server-default değişimi = 0"* | **YANLIŞ** — aynı koşuda **60 `modify_default`** işlemi de var | **DÜZELTİLDİ** |

Son satır bu koşunun bulgusudur: rapor yalnız `compare.constraints`'in
`Detected added/removed …` satırlarını saymış; `compare.server_defaults` farklı bir cümle
kurar (`Dialect impl … detected server default on column X`) ve o taramaya takılmamıştır.
Sapmalar `alembic check`'in **ERROR** satırındaki operasyon listesinde her zaman vardı.

### Sapmaların şekli

39'unun tamamı **yalnız ADLANDIRMA**: sevk edilen kısa ad (`ix_backtest_run_snapshot`)
karşısında modelin `index=True`'dan türettiği SQLAlchemy varsayılanı
(`ix_backtest_run_composition_snapshot_id`). Kolon kümesi, uniqueness ve partial-predicate
**aynı**. Bu yüzden **fix tipi 1** uygulandı: migration'a dokunulmadı, model sevk edilen ada
hizalandı (`__table_args__` içinde `Index("<sevk edilen ad>", "<kolon>")` — dosyanın zaten
kullandığı ev stili). **Sevk edilen adlar DB'den okundu, tahmin edilmedi.**

40'ıncı sapma (`agent_event.seq`) yapısaldır ama yine **DB'ye dokunmadan** kapandı: model
artık migration'ın sevk ettiği şekli bildiriyor — `unique=True` (⇒ `agent_event_seq_key`)
**ayrı** ve `Index("ix_agent_event_seq", "seq")` **ayrı**.

## 2. P4-2 fonksiyonel etkisizliği — deneysel kanıt

Aynı `seq` değeriyle iki satır eklendi:

```
alembic yolu   : ERROR duplicate key value violates unique constraint "agent_event_seq_key"
create_all yolu: ERROR duplicate key value violates unique constraint "ix_agent_event_seq"
```

Uniqueness **iki yolda da uygulanıyor**; ayrışan tek şey hata mesajındaki constraint adıdır.
`seq` zaten `Identity()` ile DB tarafından üretildiğinden ORM yolundan duplicate erişilebilir
değil. Fazladan non-unique index'in maliyeti yalnız yazma + depolamadır. **Semantik etki yok.**
Fazladan index **kaldırılmadı**: bir index'i düşürmek veya uniqueness'ını çevirmek ayrı bir
karardır ve bu PR veri kaybettiren hiçbir index işlemi yapmaz.

## 3. Kapanış ölçümü

| Ölçüm | Önce | Sonra |
|---|---|---|
| `alembic check` index-ekseni operasyonu | **40** (`add_index` 40 / `remove_index` 40 / `remove_constraint` 1) | **0** |
| Kurulum yolu index paritesi (alembic ↔ `create_all`) | **DIVERGENT** — 361 vs 360, 40 only-alembic / 39 only-create_all / 1 differing | **BIT-IDENTICAL** — 361 vs 361, 0 / 0 / 0 |
| `alembic check` exit | 255 | **255** (aşağı bakınız) |
| `add/remove column`, `add/remove table` | 0 | **0** |
| alembic head | `0043_i08_registry_strategy_fks` | **değişmedi** (bu dalgada migration yok) |

### `alembic check` NEDEN hâlâ 255

Kalan tek sınıf **60 `modify_default`** (40 tabloda 60 kolon): DB'de bir server default var,
model onu **yalnız Python tarafında** (`default=`, `server_default=` olmadan) bildiriyor —
ör. `backtest_result.deletion_state`, `backtest_result.row_version`, `agents.enabled`.
Bu, P4-2 ile **aynı aileden** gerçek bir model↔migration ayrışmasıdır (create_all yolu o
kolonları DB-seviyesi default olmadan kurar), ama **P4-1/P4-2 kapsamında değildir**: modele
`server_default` eklemek `create_all`'ın ürettiği şemayı değiştirir, dolayısıyla ayrı bir
karar ve ayrı bir PR'dır. **Bu koşuda ölçüldü, düzeltilmedi.**

## 4. Bağlanan kapı — ve neyi ÖLÇMEDİĞİ

`scripts/schema_parity_gate.py`, `ci.yml` `backend` job'ında `alembic upgrade head`'in
**hemen ardından** koşar (migration yolunun gerçeğini o veritabanından okur).

**Assert ettikleri:** (1) alembic yolu ile `create_all` yolunun index kümesi **bit-özdeş**
(ad + kolon + uniqueness); (2) autogenerate **sıfır** index/constraint ekseni operasyonu
emitler; (3) server-default sapma sayısı **60'ı geçemez** (tavan — düzeltilmemiş bir sorun
öylece kalabilir ama yayılamaz); (4) başka hiçbir şema drift'i yok (kolon/tablo/tip).

**Assert ETMEDİĞİ:** **`alembic check`'in exit code'u.** O komut hâlâ 255'tir ve kapı bunu
sıfırmış gibi göstermez. Kapının adı da bunu söyler: *index axis*.

`alembic check`'in kendisi bu iki kalem için **yetersizdir**: operatör sınıfı taşıyan dört
`audit_events` expression index'ini (`gin_trgm_ops`, `varchar_pattern_ops`) **atlar** ve
"eşit varsayar". Kurulum-yolu karşılaştırması onları gerçek `pg_get_indexdef` üzerinden
görür — kapının (1) numaralı assertion'ı bu yüzden `alembic check`'ten **daha güçlüdür**.

### Kapı gerçekten kırmızıya dönüyor mu — negatif kanıt

İki sapma tipi de geçici olarak geri konuldu; ikisinde de **exit 1**:

| Enjekte edilen | Kapının tepkisi |
|---|---|
| P4-1 tipi: `ix_artifact_link_source` pinini kaldır, `index=True`'ya dön | `[1]` MIGRATION-ONLY + CREATE_ALL-ONLY, `[2]` `remove_index`+`add_index` → **FAIL** |
| P4-2 tipi: `seq`'te `unique=True, index=True`'yu tek unique index'e çök | `[1]` MIGRATION-ONLY `agent_event_seq_key` + DIFFERS `ix_agent_event_seq`, `[2]` 3 op → **FAIL** |

Ham çıktı: `p4_parity_gate_negative.txt`. Geri alındıktan sonra kapı yeniden **exit 0**
(`p4_parity_gate_green.txt`).

## 5. Migration disiplini

Bu dalga **migration eklemedi** — sapmaların hepsi model tarafında kapandı. Yine de doğrulandı:
tek head (`0043_i08_registry_strategy_fks`), `alembic/versions/*.py` = **43 dosya**, boş
şemadan `upgrade head` → `downgrade -1` → `upgrade head` **4 koşunun 4'ünde exit 0**, son
`alembic current` = `0043 (head)`. Kolon paritesi kapının `[4]` assertion'ı ile **0 problem**.
`ENGINE_VERSION` değişmedi; `docs/openapi.json` değişmedi; ürün davranışı değişmedi.
