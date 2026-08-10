<!-- doc-status: historical -->
> **EVIDENCE RECORD — 2026-08-07.** Bu belge o gün, o ağaç üzerinde koşulan migration ve
> şema kanıtının kaydıdır. Sayılar koşuldukları anın değerleridir; güncel otorite
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 29 / P4 — Migration ve şema kanıtı

**Verdict: PASS — BLOCKED değil.** Beş adımın beşi de geçti. Bulunan tek gerçek sapma
şema *index adlandırmasında*dır, kolonlarda değil; bu dalga tarafından getirilmemiştir ve
hiçbir CI kapısı tarafından izlenmemektedir (§Dürüst sınırlar).

## Ağaç ve ortam

| | |
|---|---|
| HEAD | `1f4b88b` (`origin/main` ile aynı) |
| Branch | `claude/entropia-v18-migration-proof-392b87` (worktree) |
| Working tree | temiz (`git status --porcelain` boş) |
| PostgreSQL | 16.14 (Homebrew), `localhost:5432` |
| alembic | 1.18.5 |
| Python | 3.12.13 |
| `LC_ALL` | `en_US.UTF-8` |
| İzole DB | `entropia_p4_proof` (bu koşu için `CREATE DATABASE`, başka hiçbir oturumla paylaşılmıyor) |
| `DATABASE_URL` | `postgresql+asyncpg://entropia:***@localhost:5432/entropia_p4_proof` |
| `TEST_DATABASE_URL` | aynı URL'ye set edildi |

> **Sürücü notu (dürüst kayıt).** Görev `TEST_DATABASE_URL` ile izolasyon istedi; alembic
> ise `alembic/env.py` üzerinden `entropia.config.Settings.database_url`, yani
> **`DATABASE_URL`** okur. İkisi de aynı izole `+asyncpg` URL'sine set edildi — istenen
> izolasyon sağlandı, ama izolasyonu fiilen taşıyan değişken `DATABASE_URL`'dir.

## 0. Head karşılaştırması — `repository_facts.md` (BLOCKED kapısı)

| Kaynak | Alembic head | Revizyon sayısı |
|---|---|---|
| `docs/generated/repository_facts.md` §Summary | `0043_i08_registry_strategy_fks` | 43 (single head) |
| Canlı `alembic heads` (bu koşu) | `0043_i08_registry_strategy_fks` | 43 dosya, 1 head satırı |

**ÇELİŞKİ YOK → BLOCKED değil.** Ek olarak üreteç kapısı bağımsız doğrulandı:

```
uv run python ../scripts/generate_repository_facts.py --root .. --check
→ exit 0 — "documentation-truth gate OK — artefacts fresh, documents classified, no stale claims."
```

---

## 1. Boş DB'den `alembic upgrade head`

```
psql -d entropia_p4_proof -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE;" -c "CREATE SCHEMA public;"
uv run alembic upgrade head
```

| Alt adım | exit code |
|---|---|
| Şema sıfırlama (`DROP SCHEMA public CASCADE; CREATE SCHEMA public;`) | **0** |
| `alembic upgrade head` | **0** |

- Uygulanan migration sayısı: **43** (`Running upgrade` satırı sayısı), `0001` → `0043`
  zincirinin tamamı tek koşuda.
- Son satır: `Running upgrade 0042_package_import_source_name -> 0043_i08_registry_strategy_fks, I-08 slice 1 — put the registry-owner and strategy head/family edges under the DB`

Kurulan şemanın büyüklüğü, `repository_facts.md` ile karşılaştırmalı:

| Ölçüm | Bu koşu | `repository_facts.md` | |
|---|---|---|---|
| Base table | 105 (`alembic_version` dahil) → **104** (hariç) | 104 | ✅ |
| Foreign key | **140** | 140 | ✅ |

## 2. Single-head doğrulaması

```
uv run alembic heads     → exit 0
uv run alembic current   → exit 0
```

`alembic heads` çıktısı **tek satır**:

```
0043_i08_registry_strategy_fks (head)
```

`alembic current` aynı revizyonu bildiriyor: `0043_i08_registry_strategy_fks (head)`.
`alembic/versions/*.py` dosya sayısı **43** — head sayısı 1, yani dallanma yok.

## 3. Son migration: down/up/down/up — veri koruma kanıtı

Son migration `0043_i08_registry_strategy_fks` **yalnızca üç FK kısıtı** ekler
(veri taşımaz):

- `entity_registry.owner_principal_id` → `principals.principal_id`
- `strategy_root.current_revision_id` → `strategy_revision.revision_id`
- `strategy_root.rationale_family_id` → `rationale_family_root.entity_id`

Bu yüzden veri koruma kanıtı, migration'ın **dokunduğu beş tabloya** tohum satır yazıp
her fazda satırların bit düzeyinde aynı kaldığını ölçer. Fingerprint = tablo başına
`md5(string_agg(satırın tam text hâli, sıralı))` — tek bir kolonun değişmesi bile
fingerprint'i kaydırır.

Tohumlama (FK sırasına göre: `principals` → `entity_registry` → `rationale_family_root`
→ `strategy_revision` → `strategy_root`): **exit 0**, 5 tabloda 6 satır.

| Faz | Komut | exit | `alembic current` | 0043'ün 3 FK'si | Veri fingerprint |
|---|---|---|---|---|---|
| baseline | — | — | `0043…` (head) | 3/3 mevcut | referans |
| down 1 | `alembic downgrade -1` | **0** | `0042_package_import_source_name` | 0/3 (üçü de düştü) | **IDENTICAL** |
| up 1 | `alembic upgrade head` | **0** | `0043…` (head) | 3/3 geri geldi | **IDENTICAL** |
| down 2 | `alembic downgrade -1` | **0** | `0042_package_import_source_name` | 0/3 | **IDENTICAL** |
| up 2 | `alembic upgrade head` | **0** | `0043…` (head) | 3/3 | **IDENTICAL** |

Dört fazın dördünde de beş tablonun fingerprint'i ve satır sayıları baseline ile
**birebir aynı**; downgrade hiçbir satırı düşürmedi, upgrade hiçbir satırı yeniden
yazmadı. Kısıtlar tam olarak beklendiği gibi gidip geldi.

## 4. Migration ↔ model kolon parity taraması

İki bağımsız tarama koşuldu.

### 4a. Kolon parity (asıl istenen tarama) — **exit 0, sıfır sapma**

Alembic'in kurduğu DB'nin `information_schema.columns` dökümü, `Base.metadata` ile tablo
tablo karşılaştırıldı (tablo varlığı + kolon varlığı + NULL/NOT NULL verdict'i):

```
tables compared: 104
columns compared: 1157
problems: 0
```

Tek yönlü hiçbir tablo, tek yönlü hiçbir kolon, tek bir nullability farkı yok.
**Migration ile model kolon düzeyinde tam örtüşüyor.**

### 4b. `alembic check` (üst küme) — exit 255, ama **kolon farkı sıfır**

`alembic check` (env.py'de `compare_type=True`, `compare_server_default=True`) kırmızı
döndü. Emitlediği farkların **tamamı** index/constraint düzeyinde:

| Fark sınıfı | Adet |
|---|---|
| `Detected removed index` | 39 |
| `Detected added index` | 39 |
| `Detected removed unique constraint` | 1 |
| `Detected changed index` (unique=False → True) | 1 |
| **`Detected added/removed column`** | **0** |
| **`Detected added/removed table`** | **0** |
| **tip / server default değişimi** | **0** |

Yani `alembic check`'in kırmızısı 4a'nın yeşiliyle çelişmiyor: kolon ekseni temiz,
kırmızı olan eksen index adlandırması.

### 4c. Index farkları gerçekten "sadece ad" mı? — evet, iki istisna dışında

Bir index'in **ne yaptığına** göre (tablo + sıralı kolon demeti + uniqueness)
karşılaştırma:

```
shapes in DB: 254   shapes in model: 253
same shape, different name (RENAME ONLY): 48
shape present in DB only  (model lacks coverage): 2
shape present in model only (DB lacks coverage): 1
```

- **48 aynı-şekil-farklı-ad**'ın **8'i sapma bile değil**: model tarafında unique
  constraint isimsiz bırakılmış, adı Postgres veriyor (`auth_sessions_token_hash_key`,
  `backtest_result_run_id_key` …). Kalan **40'ı** gerçek ad sapmasıdır ve tek bir
  desendedir — migration kısaltılmış ad yazıyor, model SQLAlchemy'nin otomatik adını
  kullanıyor: `ix_agent_event_task` (migration) ↔ `ix_agent_event_task_id` (model),
  `ix_backtest_result_fingerprint` ↔ `ix_backtest_result_composition_fingerprint`, …
  **Hiçbirinde index kapsaması kaybolmuyor**, sadece ad farklı.
- **`trash_entries(deleted_at DESC, id DESC)` bir yanlış pozitif.** Bu bir *expression*
  index; SQLAlchemy `Index(..., text("deleted_at DESC"), text("id DESC"))` için
  `index.columns`'ı boş bırakır, karşılaştırıcım da kolonları okuyamaz. Kaynağa bakıldı:
  `models/deletion.py:29` ile `alembic/versions/0018_trash_page.py:55-59` **aynı adı ve
  aynı ifadeleri** yazıyor. Sapma yok.
- **`agent_event.seq`'te tek gerçek şekil farkı var, ama uniqueness iki tarafta da
  garanti.** Migration `0016_analysis_lab.py:224` kolonu `unique=True` ile yaratıyor
  (Postgres `agent_event_seq_key` unique constraint'i üretiyor) ve satır 238'de **ayrıca**
  non-unique `ix_agent_event_seq` açıyor. Model (`agent_lab.py:252-254`) aynı şeyi tek
  nesneyle ifade ediyor: `unique=True, index=True` → tek **unique** index
  `ix_agent_event_seq`. Sonuç: unique'lik iki tarafta da uygulanıyor; alembic'in kurduğu
  DB'de fazladan, gereksiz bir non-unique index duruyor. Fonksiyonel bir kayıp değil,
  ölçülebilir bir fazlalık.

## 5. FK insert-order (L1) kanıtı

**Bu dalgada yeni `create_*` YOK.** Bu iddia varsayım değil, ölçüm:

- ADIM 29 (`1f4b88b`, PR #631) yalnız `docs/`, `CLAUDE.md` ve
  `scripts/generate_repository_facts.py` dosyalarına dokundu — 12 dosya, sıfır
  `backend/src`, sıfır `backend/alembic`.
- `git diff 20e942b^..HEAD -- backend/` **boş**: ADIM 28–29 aralığında backend hiç
  değişmedi.
- `src/` ağacına dokunan en son commit **`780dc92`** (#622, ADIM 25);
  `alembic/versions/` ağacına dokunan en son commit **`d0067bb`** (0043'ü getiren I-08
  slice'ı). İkisi de bu dalgadan önce.
- `git diff … | grep '^\+.*def create_'` → **(none)**.

Referans için: `application/commands/` altında hâlihazırda **25** `create_*` komutu var;
hiçbiri bu dalgada eklenmedi veya değiştirilmedi, dolayısıyla yeni bir L1 kanıtı gereken
yüzey yok.

**Tesadüfi ama gerçek L1 kanıtı (dar kapsam).** §3'ün tohumlaması, 0043'ün üç FK'si
**canlıyken** `principals` → `entity_registry` → `rationale_family_root` →
`strategy_revision` → `strategy_root` sırasıyla tek transaction içinde koştu ve **exit 0**
verdi. Bu, 0043'ün getirdiği üç kenar için insert-order'ın tutarlı olduğunu gösterir —
ama **yalnız o üç kenar için**; 25 `create_*` komutunun tam L1 taraması değildir ve öyle
okunmamalıdır.

---

## Dürüst sınırlar

1. **`alembic check` bu repoda kırmızı ve hiçbir CI kapısı onu koşmuyor.**
   `.github/workflows/*.yml` içinde `alembic upgrade head` var (`ci.yml:111`,
   `performance.yml:100`, `install-acceptance.yml`), **`alembic check` yok**. Yani
   §4b'deki 40 index-adı sapması sahipsiz, izlenmeyen, duran bir durumdur. Bu dalga onu
   *getirmedi* ve bu dalga onu *düzeltmedi* — sadece ölçtü. Düzeltmek migration yazmayı
   gerektirir (index rename) ve bu bir ürün/sıra kararıdır.
2. **`agent_event.seq` üzerindeki fazladan non-unique index** alembic yolunda kalır;
   `Base.metadata.create_all` ile kurulan test şemasında yoktur. İki kurulum yolu bu tek
   noktada bit-özdeş değildir. Fonksiyonel etkisi yok (unique'lik iki tarafta da var),
   yazma maliyeti minimal, ama "alembic şeması ile test şeması byte-identical" cümlesi
   bu index için **doğru değildir**.
3. **Kolon parity taraması tip karşılaştırması yapmaz** — kolon varlığı ve nullability'yi
   ölçer. Tip ekseni `alembic check`'in `compare_type=True` koşusuyla kapatıldı (sıfır tip
   farkı bildirdi), yani eksen boş kalmadı; ama iki farklı araçla kapatıldı, tek araçla
   değil.
4. **Veri koruma kanıtı 0043'ün dokunduğu beş tabloyla sınırlıdır.** 104 tablonun
   tamamına tohum atılmadı. 0043 veri taşımayan saf bir FK migration'ı olduğu için bu
   kapsam yeterlidir; veri taşıyan bir migration için yeterli olmazdı.
5. **`alembic downgrade -1` yalnız son migration'ı geri alır.** Zincirin tamamı için
   `downgrade base` koşulmadı — istenen kanıt "latest migration" döngüsüydü ve o koşuldu.

## Yeniden üretme

```bash
cd backend
export LC_ALL=en_US.UTF-8
export DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_p4_proof"
psql -h localhost -p 5432 -U entropia -d postgres -c "DROP DATABASE IF EXISTS entropia_p4_proof;" -c "CREATE DATABASE entropia_p4_proof OWNER entropia;"
psql -h localhost -p 5432 -U entropia -d entropia_p4_proof -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE;" -c "CREATE SCHEMA public;"
uv run alembic upgrade head && uv run alembic heads && uv run alembic current
uv run alembic downgrade -1 && uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head
uv run python ../scripts/generate_repository_facts.py --root .. --check
```
