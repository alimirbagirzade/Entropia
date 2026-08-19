<!-- doc-status: current -->
# `C4`'ün worker'ı containment importer guard'ına GÖRÜNÜR mü olmalı?

> **KARAR İMZALANDI (2026-08-19): Seçenek A (#799).** Bu belge bir **hazırlık** olarak
> yazıldı ve hiçbir seçeneği seçmiyordu; imza §Karar'da, doldurulmuş hâlde durur.
> Aşağıdaki ölçümler imza öncesi hâliyle **değiştirilmeden** korunmuştur.
>
> Çerçeve: `C4` (E5) worker'ı paylaşımlı saat dalına bağlar. Bunu yapmanın **iki** yolu var
> ve ikisi de sevk edilebilir durumda — **iki ayrı açık PR olarak yazıldılar** (#799 ve #800).
> Fark bir üslup tercihi değil: biri 2026-08-18'de **imzalanmış** bir allowlist'i olduğu gibi
> bırakır, diğeri onu **ikinci kez genişletir**. #731 ve `CLAUDE.md` §ADIM 69/70 bu ikinci
> hamleyi açıkça *"allowlist genişletmesi İNSAN incelemesidir"* diye işaretliyor — o yüzden
> karar bir insana ait. `closure_participant_importer_allowlist_2026-08-18.md` ile aynı
> disiplin, bir seviye yukarısı.

- **Tarih:** 2026-08-19
- **Base:** ölçüm `origin/main` @ `a5b46ab0`'a karşı yapıldı; belge `ee5ab384`'e rebase
  edildi. **Ölçümler ayakta:** aradaki iki merge (#796 dependabot, #797 ADIM 88)
  `git diff --name-only a5b46ab0 ee5ab384` ile tarandı — `backend/src`'te ve üç guard
  dosyasının (`test_backtest_unified_clock.py`, `test_backtest_item_intents.py`,
  `test_oracle_portfolio_containment_gate.py`) hiçbirinde **sıfır satır**; değişen her şey
  `docs/`. Yani §Ölçüm 2'nin tablosu yeniden ölçülmedi çünkü **ölçülecek bir şey oynamadı**.
- **Kapsam:** yalnız **importer** kontrolü — `test_backtest_unified_clock.py` ve
  `test_backtest_item_intents.py` içindeki per-modül allowlist'ler. `test_oracle_portfolio_containment_gate.py`'ın
  **çağıran** daraltması (`assert callers == []` → `_AUTHORISED_*_CALLERS`) bu kararın
  kapsamı **DIŞINDADIR**: iki PR de onu aynı şekilde ve zorunlu olarak yapıyor, çünkü `C4`'ün
  tanımı bunu içeriyor (`STAGE2_HANDOFF.md` §Next, ADIM 85 bloğu).
- **Yazarın rolü:** hazırlık. **Karar ürün sahibine aittir ve §Karar'da imzalanmıştır.**
- **Bloklar:** `C4`. `C4` inmeden `C6` → `C7` → `C8` → `C9` zinciri de açılamaz.

---

## Ölçüm 1 — Sorunun teknik kaynağı

`_EngineParticipant`'ı worker'dan kurmak iki tipe ihtiyaç duyar: **`ItemIdentity`** ve
**`ItemBarStream`**. İkisi de contained unified-clock modüllerinde yaşıyor. Yani worker
faz döngüsünün *çağıranı* olmak zorunda; sorulan şey **importer'ı da olup olmayacağı**.

## Ölçüm 2 — İki PR'ın fiilî yüzeyi (`a5b46ab0`'a karşı `git diff --name-only`)

| | **#799** (`feat/closure-c4-worker-branch`) | **#800** (`feat/closure-c4-worker-guarded-allowlist`) |
|---|---|---|
| `backend/src` dosyası | **2** — `jobs/backtest_engine.py`, `domain/backtest/participant.py` | **1** — `jobs/backtest_engine.py` |
| worker importer mı | **HAYIR** — fabrika `participant.py`'de | **EVET** — tipleri doğrudan import eder |
| genişletilen per-modül allowlist | **0** | **2** — `execution.clock`, `execution.intents` |
| `test_backtest_portfolio_ledger.py` / `..._arbitration.py` | el değmedi | el değmedi (ölçüldü: worker onları import etmiyor) |
| containment gate çağıran daraltması | evet | evet |
| kapanış ritüeli | **var** (`ADIM 88` iddiası) | **yok, bilerek** |

**Her iki PR de aynı şeyleri KORUYOR** (ikisinde de ölçüldü): `SHARED_ALLOCATION_STATUS` =
`future_dev`, admission her paylaşımlı koşuyu hâlâ reddediyor, `ENGINE_VERSION` değişmedi,
migration yok, OpenAPI değişmedi, **50 golden digest bayt bayt aynı**, `combine_item_runs(`
ve `for prepared in prepared_items:` assertion'ları yerinde ve yeşil.

## Seçenek A — Fabrika `participant.py`'de, allowlist'e DOKUNMA (#799)

Worker faz döngüsünün **çağıranı** olur ama **importer'ı** olmaz. 2026-08-18'de imzalanan
tek-modüllü allowlist aynen kalır; ikinci bir insan kararı gerekmez.

- **Lehine:** imzalı kapsamın içinde kalır. `C4` bugün inebilir. Worker'ın contained tiplere
  bağımlılığı tek bir yerde (`participant.py`) toplanır ve o modül zaten bu iş için var.
- **Aleyhine — ve bu ölçülmüş bir maliyet:** worker'ın contained alt sisteme **yeni uzanımı
  guard'a GÖRÜNMEZ**. İzinli bir modülün arkasından geçer. Guard yeşil kalır ama artık
  *daha az şey* garanti eder: "worker bu tipleri import etmiyor" doğrudur, "worker bu
  tiplere erişmiyor" **yanlıştır**.

## Seçenek B — Tipleri worker'da import et, allowlist'i AÇIKÇA genişlet (#800)

Guard kırmızıya döner ve allowlist **tek adlandırılmış modülle**, gözden geçirilebilir bir
diff'te genişler.

- **Lehine:** `C3`'ün imzalandığı gerekçenin birebir aynısı, bir seviye yukarısı. O karar
  adaptörü `execution/` **dışına** koydu çünkü içeride *"assertion'ı yapı gereği atlatır, bu da
  guard'ı tatmin etmez KÖR eder"* idi. Fabrikayı izinli bir modülden geçirmek aynı hamledir.
  *Bilerek genişletilmiş bir guard, hiç sorulmamış bir guard'dan daha değerlidir.*
- **Aleyhine:** imzalı karar **bir** modül ölçmüştü; bu **ikinci** genişletmedir ve #731'e göre
  ayrı bir insan incelemesi ister — yani bu belge. `C4` imza gelene kadar bekler.

## Seçenek C — Başka

Örn. tipleri contained olmayan bir modüle taşımak (yapısal iş, iki PR'ın da kapsamı dışında),
ya da guard'a "izinli çağıran üzerinden dolaylı erişim" kavramı eklemek (guard'ın kendisini
değiştirir — kapsam dışı ve daha riskli).

---

## Karar — İMZALANDI

**Seçenek:** ☑ **A (#799)** ☐ B (#800) ☐ C (başka: ______________________)

**Gerekçe (bir cümle yeterli):**

```
2026-08-18'de imzalanmış tek-modüllü allowlist'in kapsamı içinde kalınır; ikinci bir
importer genişletmesi C4'ü bir imza daha beklerken bloklamasın diye Seçenek A seçildi.
Seçenek A'nın bu belgede ÖLÇÜLMÜŞ bedeli — worker'ın contained alt sisteme uzanımının
guard'a GÖRÜNMEZ olması — kabul edilmiş bir honest boundary'dir, gözden kaçmış değildir.
```

- **karar veren:** alimirbagirzade (ürün sahibi)
- **tarih:** 2026-08-19

### İmzadan sonra ne olur

- Kazanan PR güncel `main`'e rebase edilir, **ADIM numarası o an yeniden ölçülür**
  (#799 bugün `ADIM 88` yazıyor ama `88` **#797**'nin, o yüzden en az `89` olacak).
- Kaybeden PR **kapatılır**; kendine özgü ölçümleri kapatma yorumuna yazılır — özellikle
  **#800'ün iki bulgusu**, çünkü ikisi de hangi PR inerse insin geçerlidir:
  1. **Sevk edilen şema varsayılanlarıyla hiçbir strateji co-simulate edemez.** Zorlanmış
     bayrakla standart fixture adaptörün on bir reddinden **üçüne** birden takılıyor
     (`entry_timing`/`exit_timing` = `next_candle_open`, `same_direction_stacking` =
     `allow_stacking`). Fail-closed davranış **doğru** olan; ama `C6`'nın bu listeyi admission
     blocker'ına çevirmesi bir **ürün kararıdır**.
  2. **Gate'in substring assertion'ları göründüğünden zayıf.** `assert "shared_allocation_requested"
     in worker` conjunct return ifadesinden **silinse bile yeşil kalıyor**, çünkü ad
     `_use_unified_clock`'un docstring'inde de geçiyor. Negatif kontrolle ölçüldü.
     Taşıyıcı pin davranışsal olmalı; substring yalnız "guard toptan silindi mi" sorusunu
     yakalar, "inceltildi mi" sorusunu değil.
