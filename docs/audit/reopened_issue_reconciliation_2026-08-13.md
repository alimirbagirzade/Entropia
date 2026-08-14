<!-- doc-status: historical -->
> **HISTORICAL RECORD — bir ÖLÇÜM KAYDIDIR, güncel handoff değildir.** 2026-08-13'te
> `6a05118` üzerinde ölçülen durumu dondurur. Bir issue'nun durumu bu belge yazıldıktan
> sonra değişebilir; **bu dosya onu takip etmez.** Güncel otorite: `CLAUDE.md`
> §Current position. Yöntem ve bağlam:
> `docs/audit/final_closure_forensic_audit_2026-08-13.md`.

# Toplu yeniden açılan 21 issue — kodla karşılaştırma

## Neden var

2026-08-13 `10:33:36–10:33:44Z` arasında — **8 saniyede, artan issue numarası sırasıyla,
hiçbirine yorum düşülmeden** — repodaki kalan **tüm** kapalı issue'lar toplu olarak yeniden
açıldı. Sonuç: repoda kapalı yalnız 2 issue kaldı (`#617`/`#618`, PD-7), yani **"kapalı"
sinyali hiçbir bilgi taşımıyor** ve simetrik olarak **"açık" sinyali de taşımıyor**.

Bu belge o 21 issue'nun her birinin **kodda gerçekten açık olup olmadığını** ölçer. Amaç
issue durumu değiştirmek değil — **kararı ölçülmüş bir listeye dayandırmak**. Hiçbir issue
bu ölçüm sırasında kapatılmadı veya açılmadı; issue durumu **insan kararıdır**.

## Sonuç

| Sınıf | Sayı | Issue'lar |
|---|---|---|
| **ONARILMIŞ** — açık ama kod düzeltilmiş | **7** | `#515` `#533` `#539` `#549` `#556` `#557` `#591` |
| **KISMİ** — bazı alt iddiaları düşmüş, bazıları canlı | **1** | `#541` |
| **GERÇEKTEN AÇIK** | **13** | `#532` `#534` `#535` `#536` `#540` `#542` `#543` `#544` `#545` `#546` `#547` `#582` `#677` |

13 açığın **6'sı ürün kararıdır** (`product-decision`: `#535` `#542` `#543` `#544` `#545`
`#546`) — kod yazarak kapanmazlar.

---

## ONARILMIŞ (7) — kapatılmaya aday

| # | İddia | Ölçüm (`6a05118`) |
|---|---|---|
| **#515** | Embedded resolver satırları ham `pkgrev_…` id basıyor | **Düzeltilmiş.** `Embedded.tsx` collapsed satırı `canonical_key` + `"active revision pinned"` / `"no active revision"` basıyor; ham id yalnız **expanded** detayda (`<code>{esp.revision_id}</code>`) — ki issue bunu **açıkça izin veriyor** (*"move the exact opaque identifier to the expanded technical detail"*). Kabul kriterinin test yarısı da var: `frontend/src/test/embedded.test.tsx:198-199` iki etiketi de pinliyor. |
| **#533** | UI, Ready Check'in varsayılan `allow_hedge`'i bloklamadığı hâlde bloklaadığını iddia ediyor | **Düzeltilmiş.** `StrategyConfigForm.tsx:745-754` artık `#533`'ü adıyla anan bir yorum ve koşullu `capabilityInertReason` taşıyor: exit-on-opposite AÇIKken *"pozisyon hedge dalına ulaşılmadan kapanır"* diyor, yalnız KAPALI dalı gerçek blocker sayıyor. Backend ile hizalı. |
| **#539** | 22 `future_dev` capability satırının 11'i sıradan seçilebilir seçenek olarak render ediliyor | **Düzeltilmiş.** Matris (import edilerek sayıldı): **62 satır, 22 `future_dev`, 9 farklı `field_path`**. Frontend genelinde `capabilityField` taraması: **9/9 field path açıklanıyor**, kapsanmayan **0**. *(Yalnız `StrategyConfigForm.tsx`'e bakan bir ölçüm 3 alanı kaçırır — üçü de `StrategyGraphForm.tsx`'te: `:786`, `:795`, `:1059`.)* |
| **#549** | Gap'lenmiş koruma stopu hâlâ ulaşılamayan stop seviyesini book ediyor | **Sevk edilmiş.** `ENGINE_VERSION`'ın **adı bile** `backtest-engine-v18-gap-adjusted-stop-fill`; `execution/fills.py::_attainable_stop_fill` + `gap_adjusted` property yerinde; issue'nun `xfail(strict)` olarak taşıdığı aritmetik artık **yok** — oracle paketinde xfail **sıfır**. |
| **#556** | `data_bundle.resolve` ikizinin blokladığı soft-deleted/deprecated revizyonları pinliyor | **Düzeltilmiş.** `jobs/agent_tools.py:420` artık `rd_jobs.admit_bundle_member` — iki yüzeyin **aynı** kapısı — üzerinden geçiyor. |
| **#557** | Feature-Input-Only kapısı çağıranın gönderdiği boolean'dan karar veriyor | **Düzeltilmiş.** `agent_tools.py:386` açıkça yazıyor: `has_approved_feature_definition` **iddiası okunmuyor**, veritabanından çözülüyor. |
| **#591** | `agent_coordinator`, scheduler'ın per-tick event-loop kusurunu taşıyor | **Düzeltilmiş.** İkisi de artık tek `asyncio.run(_loop_until_stopped())` + içeride `while not stop.is_set()` + `finally: await get_engine().dispose()`. `agent_coordinator/__main__.py:119` eski şekli (*"``asyncio.run`` per tick"*) geçmiş zamanla tarif ediyor. |

---

## KISMİ (1)

### `#541` — üç alt iddiadan **ikisi hâlâ canlı**

| Alt iddia | Ölçüm |
|---|---|
| 1. `increasing_by_layer` gerekçesi kanonu yanlış aktarıyor | **CANLI.** `capabilities.py` `dependency` metni hâlâ *"next canonical timeframe vs. doubling are different ladders"* diyor — issue bunun doc 02 §6.1 ⓘ karşısında yanlış olduğunu gösteriyor. |
| 2. Scaling-timeframe gerekçesi *"a second resampled series the replay does not build"* diyor | **CANLI.** Metin aynen duruyor; issue `_ReferenceSeries`'in o seriyi **kurduğunu** ölçmüş. |
| 3. `strategyGraph.ts` yorumu *"capability matrix disables it in the form"* diyor ama etmiyor | **DÜŞMÜŞ.** Artık ediyor: `scaling_logic.timeframe_mode` `StrategyGraphForm.tsx:795`'te `capabilityField` taşıyor. Yorum bugün **doğru**. |

→ Kapatılamaz; kapsamı **iki metin düzeltmesine** indi.

---

## GERÇEKTEN AÇIK (13)

### Kod/test işi (7)

| # | Ölçüm (`6a05118`) |
|---|---|
| **#532** | `entry_exit_collision` motor tarafından emit ediliyor (`engine.py:1867`) ama **yayımlanan taksonomide yok**: `DECISION_TRACE_EVENT_TYPES` **21 tip** taşıyor ve bu onlardan biri değil (`stop_exit_collision` var). İddia birebir geçerli. |
| **#534** | `same_candle_entry_exit` ve `stop_priority_order` **`execution/output.py`'de hiç geçmiyor** (her ikisi için 0 satır) — provenance bloğu ikisini de yayımlamıyor. |
| **#536** | Üç boşluk da canlı: (a) `overlapping_signal_policy` için **davranışsal pin yok** — `backend/tests`'te yalnız config fixture'ı olarak geçiyor, assertion yok; (b) `ignore_trade` ve `conservative_rule` **hiçbir test dosyasında yok**, `diagnostics["stop_conflict_resolution"]` **hiç assert edilmiyor**; (c) altı alanın **altısı da** `_SCHEMA_FIELDS` guard'ının dışında. |
| **#540** | Guard **14 field path'in 9'unu** kapsıyor — issue'nun sayısı birebir. Kapsanmayan 5: `data.order_config.limit.partial_fill_policy`, `data.order_config.limit.price_rule`, `position_sizing.formula_based.formula_type`, `scaling_logic.method`, `scaling_logic.timeframe_mode`. |
| **#547** | `increasing_by_layer` şemada bir literal (`config.py:794`) ama motor onu **bilerek uygulamıyor**: `execution/scaling.py:104` `return False` — fail-closed, gerekçesi yazılı (kanon rung adımını bildirmiyor). Özellik sevk edilmemiş. |
| **#582** | **Bu auditin ana bulgusuyla aynı.** `run_portfolio`'nun `backend/src` içinde **sıfır** production çağıranı var; `SHARED_ALLOCATION_STATUS = "future_dev"`. Containment kalkamaz. |
| **#677** | Lighthouse tabanları hâlâ 100'ün altında donmuş: `frontend/e2e/lighthouse-baseline.json` → `best-practices: 96`, `seo: 82` (her rota). Kusurlar düzeltilip taban sıkılaştırılmamış. |

### Ürün kararı — kod kapatamaz (6)

`#535` · `#542` · `#543` · `#544` · `#545` · `#546` — altısı da `product-decision` etiketli.
**Hiçbirinde kaydedilmiş bir karar yok:** issue yorumları **boş** (`#544` ve `#535` doğrudan
kontrol edildi), ve belgelerde yalnızca *açılmış* olarak anılıyorlar (`ADIM11_LANDED_KICKOFF.md`,
`STAGE2_HANDOFF.md`). `docs/audit/strategy_conflict_matrix_closure.md` `#535`'i ele alıyor ama
`doc-status: historical` ve kalemi *"issue → product decision"* diye bırakıyor — yani karar
değil, **kararın gerektiğinin kaydı**.

`#544` (NET) ayrıca **canlı bir üründe görünür**: `CONFLICT_POLICY_NET_V1` uyarısı hâlâ sevk
ediliyor (`domain/allocation/rules.py:220`) ve `execution/arbitration.py:152` downgrade'i
tarif ediyor. ADR 0002 §12 onu **ADIM 19'un ön koşulu** sayıyor.

---

## Yöntem ve dürüst sınırlar

* Ölçüm **statik**: kaynak okuması, AST parse'ı ve capability matrisinin **import edilerek**
  sayılması. **Hiçbir test koşulmadı** — bir assertion'ın var olduğu görüldü, geçtiği
  görülmedi. Otorite CI'dır.
* **İki ölçüm kapsam hatası yapıldı ve düzeltildi**, ikisi de aynı dersi veriyor:
  `#539`'da yalnız `StrategyConfigForm.tsx`'e bakmak 3 alanı kaçırdı (üçü `StrategyGraphForm.tsx`'te);
  capability matrisini regex'le saymak 62 yerine 35 satır buldu (çok satırlı `CapabilityOption`
  çağrıları). **Negatif bir iddiadan önce kapsamı kanıtla** — "bulamadım" ile "yok" aynı şey
  değildir.
* `#535`/`#542`/`#543`/`#545`/`#546` için ürün kararının yokluğu **issue yorumları + belge
  taraması** ile ölçüldü; `#544` ve `#535` doğrudan doğrulandı, diğer dördünde yorum listesi
  tek tek çekilmedi.
* Bu belge **hiçbir issue'nun durumunu değiştirmedi**.
