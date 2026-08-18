# `participant.py` containment gate'in importer allowlist'ini genişletir — hangi biçimde?

> **Bu belge KARAR BEKLİYOR.** `C3` (E4c) yazıldığı anda containment gate'in importer
> kontrolü **kırmızıya döner**; bu tasarımın amacıdır, kazası değil. Kırmızıyı yeşile almanın
> her yolu **bilinçli bir tripwire'a** dokunur. Bu belge o kararın bloğunu **yaratır**;
> **hiçbir seçeneği seçmez** ve "önerilen" yazmaz — `closure_g15_external_row_winner_2026-08-17.md`
> ile aynı disiplin.

- **Tarih:** 2026-08-18
- **Base:** `origin/main` @ `8151cdc` (`docs(closure-g4): brief the Max Single Position cap overflow decision (#755)`)
- **Kapsam:** `tests/unit/oracles/test_oracle_portfolio_containment_gate.py` — **yalnız** importer
  kontrolü. Aynı dosyadaki diğer dört assertion bu kararın kapsamı **dışındadır**.
- **Yazarın rolü:** hazırlık. **Bu belgede hiçbir karar verilmemiştir.**
- **Bloklar:** `C3` (E4c). `C3` bloklanmadan `C4` → `C6` → `C7` → `C8` → `C9` zinciri de açılamaz.
- **BLOKLAMAZ:** `C2` (#759, ayrı ön koşul), ADR §16 **Gate 2**, `G11`, `G12`, A-08.

---

## Taban notu (dürüstlük)

**`C2` bu belge yazılırken main'de DEĞİLDİ** (#759 açık, `Backend` koşuyor). Ölçümler
`8151cdc` (main) **artı** #759'un dalı üzerinde yapıldı ve hangisinin hangi tabandan geldiği
her satırda yazılıdır. `C2` merge edilmeden `C3` zaten başlayamaz — bu belge o ön koşulun
yerine geçmez, **yanındaki ikinci kapıyı** hazırlar.

Satır numarası bilerek yazılmamıştır (CLAUDE.md §Conventions: sembol adı yaz).

---

## Ölçüm 1 — kapı bugün ne diyor

`test_the_phase_loop_exists_but_no_production_path_reaches_it` içindeki importer kontrolü,
`_PHASE_LOOP_MODULES`'ün **altı** modülü için `execution.<ad> import` literalini `backend/src`
genelinde arar ve `parent.name == "execution"` olanları muaf tutar. Kalanlar için:

```
assert importers in ([], ["domain/backtest/portfolio_engine.py"])
```

Yani bugünkü kural: **unified-clock yüzeyi `execution/` dışından yalnız faz döngüsünün kendi
modülünden görülebilir.**

`_PHASE_LOOP_MODULES` = `execution.clock` · `execution.intents` · `execution.portfolio_ledger`
· `execution.arbitration` · `execution.attribution` · `execution.provenance`.

## Ölçüm 2 — adaptörün ihtiyaç duyduğu tipler, ve **`C2` bu tabloyu büyüttü**

`ItemParticipant`'ın imzalarında geçen tipler ve tanım yerleri (main `8151cdc` + #759 dalı):

| Tip | Tanım yeri | Kapılı mı? | Nereden geldi |
|---|---|---|---|
| `ItemBarStream` | `execution/clock.py` | **evet** | E4'ten beri |
| `ItemTickView` | `execution/clock.py` | **evet** | E4'ten beri |
| `ItemIdentity` | `execution/intents.py` | **evet** | E4'ten beri |
| `PortfolioSnapshot` | `execution/intents.py` | **evet** | E4'ten beri |
| `ItemIntent` | `execution/intents.py` | **evet** | E4'ten beri |
| `OpenPosition` | `execution/portfolio_ledger.py` | **evet** | E4'ten beri |
| **`ArbitrationDecision`** | **`execution/arbitration.py`** | **evet** | **YENİ — `C2`'nin `settle`'ı** |
| `CarryCharges` | `portfolio_engine.py` | hayır | — |
| `MandatoryExit` | `portfolio_engine.py` | hayır | — |

**Bu, P-E4 kaydının ölçümünü günceller.** O belge *"altı tip, üç modül"* diyordu; `C2`'nin
`settle(view, *, admitted: ArbitrationDecision)` imzası **dördüncü kapılı modülü** (`arbitration`)
yüzeye ekledi. Yani karar geciktikçe genişlemesi istenen yüzey **büyüyor** — bu, kararın
aciliyetini artıran ölçülmüş bir olgudur, retorik değil.

## Ölçüm 3 — `portfolio_engine.__all__` bu tiplerin **hiçbirini** yeniden ihraç etmiyor

Yedi kapılı tipin yedisi için de `__all__` içinde **0 hit**. Yani adaptör bugün bu tipleri
ancak `execution.*`'tan import ederek adlandırabilir → kontrol **zorunlu olarak** kırmızı verir.

---

## Seçenekler

### Seçenek A — allowlist'i **tek adlandırılmış modülle** genişlet

```
assert importers in (
    [],
    ["domain/backtest/portfolio_engine.py"],
    ["domain/backtest/participant.py", "domain/backtest/portfolio_engine.py"],
)
```

- **Ne korur:** beklenmeyen **üçüncü** bir importer hâlâ kırmızı verir; tripwire ölmez, **bir
  adla** genişler. Genişleme diff'te görünür ve gerekçesi bu belgeye bağlanır.
- **Ne maliyeti var:** unified-clock yüzeyi artık `execution/` dışından **iki** modülden
  görülebilir. Kapının koruduğu şey "yüzey yayılmasın"dı; bir adım yayılır.
- **Not:** joker (`glob`, `startswith`) **değil** — adlandırılmış liste. Joker, kapıyı
  sessizce sınıf-genişliğinde açardı.

### Seçenek B — adaptörü `execution/` içine koy

`domain/backtest/execution/participant.py`. Kontrol `parent.name == "execution"` olanları muaf
tuttuğu için **hiç kırmızı vermez**.

- **Ne korur:** allowlist metni hiç değişmez.
- **Ne maliyeti var:** planın `C3` satırının **adıyla reddettiği** şey budur — *"guard'ı tatmin
  etmez, **kör** eder"*. Kapı yeşil kalır ama artık hiçbir şey ölçmüyordur: yeni her adaptör
  aynı muafiyete girer ve genişleme **diff'te görünmez**.

### Seçenek C — tipleri `portfolio_engine` üzerinden yeniden ihraç et

`portfolio_engine.__all__` yedi tipi de yayımlar; `participant.py` **yalnız** `portfolio_engine`'den
import eder.

- **Ölçülmüş davranış:** kontrol `execution.<ad> import` **literalini** arar. `participant.py`
  bu literali içermeyeceği için kapı **yeşil kalır**.
- **Ne korur:** görünürde kapının kendi ifadesine uyar — *"yalnız faz döngüsünden görülebilir"*.
- **Ne maliyeti var:** yüzey yine yayılır, ama artık **bir yeniden-ihraç üzerinden aklanarak**.
  Kapı bunu ölçemez, yani A'nın görünür genişlemesi yerine B'nin körlüğünü **daha az fark
  edilir** bir biçimde üretir. Ayrıca `portfolio_engine`'in public yüzeyi yedi tip büyür.

---

## Ölçüm 4 — seçeneklerin kapı üzerindeki etkisi **koşturularak** doğrulandı

İddia edilmedi, ölçüldü. `backend/src/entropia/domain/backtest/` altına iki geçici sonda
modülü kondu, her birinde kapı koşuldu, sonra ikisi de silindi (`git status` temiz):

| Sonda | İçeriği | Kapı |
|---|---|---|
| `_tmp_probe_c.py` | yalnız `from …portfolio_engine import CarryCharges` | **exit 0 — YEŞİL** |
| `_tmp_probe_a.py` | `from …execution.clock import ItemTickView` | **exit 1 — KIRMIZI** |

Kırmızının literal metni:

```
AssertionError: execution.clock gained a production importer outside the phase loop:
['domain/backtest/_tmp_probe_a.py', 'domain/backtest/portfolio_engine.py']
```

Yani: **Seçenek C kapıyı gerçekten kör eder** (yeniden-ihraç üzerinden import kontrolü hiç
tetiklemez), ve **Seçenek A'nın çözmesi gereken kırmızı gerçekten oluşur**. İki seçeneğin de
etkisi tahmin değil, koşulmuş sonuçtur.

---

## Karar

**Seçenek: ☐ A ☐ B ☐ C ☐ (başka: ______________________)**

**Gerekçe:**

**İmzalayan:** ______________________  **Tarih:** ____________

---

## Karar ne verilirse verilsin geçerli olan sınırlar

1. **Kapının diğer dört assertion'ı bu kararın kapsamı dışındadır** — özellikle
   `assert callers == []` (üretimden `run_portfolio`'ya çağrı yok). Onu gevşetmek `C4`'ün
   işidir ve **ayrı** bir karardır.
2. **`SHARED_ALLOCATION_STATUS` `future_dev` kalır.** Bu karar containment'ı **kaldırmaz**;
   ADR §16 **Gate 2** ayrıdır ve istenmemiştir.
3. **`ENGINE_VERSION` bump yok, migration yok, OpenAPI değişikliği yok** — `C3`'ün adaptörünün
   `C4`'e kadar hiçbir çağıranı olmaz.
4. Seçenek A ya da C uygulanırsa, değişikliğin **negatif kontrolü zorunludur**: sahte bir
   ikinci/üçüncü importer eklenince kapı hâlâ kırmızı vermelidir. Aksi halde genişletme
   değil **devre dışı bırakma** yapılmış olur.
