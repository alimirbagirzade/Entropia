<!-- doc-status: current -->

# Dış kaynak sicili — hangi GitHub deposu ALINDI, hangisi ALINMADI, neden

**Bu belgenin işi tek bir şeyi önlemek: aynı depoyu ikinci kez değerlendirmek.**
Bir dış skill/plugin/MCP önerisi geldiğinde **önce buraya bak**. Satır varsa karar
verilmiştir; yoksa değerlendir ve **satırı ekle**. Vazgeçme kararı da bir karardır ve
gerekçesiyle birlikte burada durur — aksi halde her oturum baştan tartışır.

Değerlendirme tarihi: **2026-08-25** · Değerlendirilen: **17 depo** (kullanıcı listesi).
Sonuç: **1 yeni kaynak alındı** (10 skill), **2 kaynak zaten bağlıydı**, **1 kaynak zaten
uyarlanmıştı**, **13 kaynak alınmadı**.

---

## Karar ölçütü (bu depoya özgü, pazarlıksız)

Bir dış kaynak ancak **dördü birden** doğruysa alınır:

1. **Kurulum gerektirmeden çalışır.** Remote container plugin **kurmaz**
   (`.claude/README.md` §enabledPlugins). Yani `/plugin install` isteyen bir kaynak
   burada **hiç koşmaz** — alınırsa `.claude/skills/` ya da `.claude/agents/` altına
   **vendor'lanır**.
2. **Var olanı tekrar etmez.** İki rehber skill aynı şeyi farklı sözcüklerle söylerse
   model hangisine uyacağını seçer → sapma. Bu depoda sapma en pahalı kusurdur.
3. **Bu deponun karara bağlanmış kurallarıyla çelişmez.** Adjudicated invariant'lar
   (O-02, O-12, O-13, O-30, K-06, K-07), katman deseni, kapanış ritüeli ve
   *"Direct-author (no Workflow)"* kuralı bir dış skill tarafından **gevşetilemez**.
4. **Bütçesi ölçülmüştür.** Her skill açıklaması her turda bağlama girer. Ölçüldü:
   sekiz upstream SAST açıklaması tek başına **4124 char** tutuyordu ve varsayılan
   listing bütçesini (%1 ≈ 2000 char @200k) **iki katına** aşıyordu → **tüm**
   skill'lerin açıklaması kesilir ve otomatik tetikleme bozulur.

---

## ALINDI

### `utkusen/sast-skills` — MIT — 10 skill vendor'landı

FastAPI + Postgres + React bir üründe **ölçülmüş** bir yüzeye denk geliyor. Alt küme
tahminle değil **grep'le** seçildi:

| Skill | Neden alındı (ölçüm) |
|---|---|
| `sast-analysis` | **ZORUNLU ilk adım** — ötekilerin dayandığı `sast/architecture.md`'yi yazar |
| `sast-idor` | owner/rol kapısına dokunan **147 dosya** (`ensure_can_edit`, `_require_owned_workspace`, `principal_id`, `AccessDenied`) |
| `sast-missingauth` | aynı 147 dosya; dört rollü kapı (Admin/Supervisor/Agent/User) |
| `sast-businesslogic` | OCC token + Idempotency-Key + lifecycle/`deletion_state` bu ürünün **çekirdeği** |
| `sast-sqli` | `text(` / `execute(` geçen **53 dosya** |
| `sast-rce` | `package_validation.py:290` **`exec(compiled, namespace)`** — canlı bir kod-çalıştırma yüzeyi |
| `sast-fileupload` | `UploadFile`/`source_file` geçen **21 dosya**; K-07 adjudicated kapısı |
| `sast-pathtraversal` | aynı upload/depolama yolları |
| `sast-hardcodedsecrets` | istemciye giden bundle + ops dosyaları |
| `sast-report` | son adım, bulguları birleştirir |

**ALINMAYAN altı kardeş, ölçümle:** `sast-graphql` (graphql → **0 dosya**),
`sast-xxe` (lxml/xml.etree/xmltodict → **0**), `sast-ssti` (jinja2/render_template → **0**),
`sast-jwt` (jwt/jose/PyJWT → **0**), `sast-ssrf` (httpx/requests/aiohttp → **0**),
`sast-xss` (`dangerouslySetInnerHTML` → **0**; React öntanımlı olarak kaçırır).
**Yüzey açılırsa satırı yeniden değerlendir** — bunlar "kötü skill" değil, bugün
**boş küme** üzerinde koşacak skill'lerdir.

**İki bilinçli değişiklik, ikisi de burada yazılı:**

1. **`description` alanları yeniden yazıldı, GÖVDELER BİREBİR KORUNDU.** Gerekçe
   yukarıdaki 4. ölçüt: 4124 → **1821 char**. Kısaltma tetiklemeyi bozmaz,
   **düzeltir** — yeni açıklamalar bu deponun kendi sembollerini adlandırır
   (`assert_supported_source_file`, `ensure_can_edit`, `package_validation.py`), yani
   skill doğru anda kendiliğinden yüklenir.
2. **`skills-lock.json`'a GİRMEDİ.** Depo skill'leri `sast-files/.claude/skills/`
   altında tutuyor; `npx skills` bu iç içe yerleşimi çözmez. Sürüm takibi bu yüzden
   **elle**: yükseltirken depoyu klonla, gövdeleri karşılaştır, açıklamaları koru.
   Sahte bir hash yazmak, kapıyı çalışıyormuş gibi göstermek olurdu.

**Ölçülmüş sınır — bunlar bir DENETÇİDİR, bir DÜZELTİCİ DEĞİL.** Çıktı `sast/`
altına yazılır (`.gitignore`'da). Bir bulguyu düzeltmeden önce
`entropia-canonical-rules` ile doğrula: taramanın *"doğrulama ekle"* ya da *"zarfı
değiştir"* önerisi, karara bağlanmış bir alanı **gevşetiyor** olabilir.

---

## ZATEN BAĞLIYDI (bir şey yapılmadı)

| Depo | Nerede | Not |
|---|---|---|
| `DeusData/codebase-memory-mcp` | `.mcp.json`, **`@0.10.2` pinli** | Sembol arama; taze container'da indeks **boştur** → `index_repository` çağır |
| `rohitg00/agentmemory` | `.mcp.json` → `scripts/memory_mcp.sh` | Slice hafızası; `node scripts/memory_index.mjs --sync` ile hidrate edilir |
| `dietrichgebert/ponytail` | `.claude/skills/ponytail-entropia`, `ponytail-audit-entropia` | **Uyarlanmış** hâli kullanılır; çıplak upstream bu depoda **koşturulmaz** |

---

## ALINMADI (ve her satır bir kez karara bağlandı)

| Depo | Karar | Ölçülmüş gerekçe |
|---|---|---|
| `multica-ai/andrej-karpathy-skills` | ❌ | Ölçüt 2. *Think before coding / simplicity / surgical / goal-driven* dördü de karşılanıyor: ilk ikisi **`ponytail-entropia`**, üçüncüsü **`entropia-scoped-fix`**, dördüncüsü **`entropia-verifier`**. Farkı: bizimkiler **pazarlıksız override listesini** taşır, upstream taşımaz → çelişirse hangisi kazanır belirsiz. |
| `github/spec-kit` | ❌ | Ölçüt 2+3. Bu depo **zaten** spec-driven: `docs/spec/NN_*`, `STAGE_BUILD_PLAN.md`, kickoff/handoff ritüeli, `check_classification` kapısı. `/specify`→`/plan`→`/tasks` **rakip** bir yöntem dayatır. |
| `rebelytics/one-skill-to-rule-them-all` | ❌ | Ölçüt 3. Kendi kendine evrilen bir skill katmanı, *STALE-BY-DEFAULT* + insan-adjudication kültürünün tersidir: kural değişikliği burada **imzalanır**, gözlemden türetilmez. |
| `mukul975/Anthropic-Cybersecurity-Skills` | ❌ | Ölçüt 4. **818 skill** — listing bütçesini yok eder. Kapsanan ihtiyacı 10 SAST skill'i zaten karşılıyor. |
| `jeremylongshore/claude-code-plugins-plus-skills` | ❌ | Ölçüt 1+4. **443 plugin / 3069 skill** aynalayan bir marketplace; plugin remote'ta kurulmaz, tedarik zinciri yüzeyi devasa. |
| `ruvnet/ruflo` | ❌ | Ölçüt 3. Swarm/meta-harness; `CLAUDE.md` backend slice'ları için **"Direct-author (no Workflow)"** diyor. Doğrudan çelişir. |
| `Egonex-AI/Understand-Anything` | ❌ | Ölçüt 2. Kod grafiği = **`codebase-memory-mcp`**, zaten bağlı ve **pinli**. |
| `thedotmack/claude-mem` | ❌ | Zaten ölçülmüştü (plugin README): MCP sunucusu değil **kurulum aracı** (Bun worker + SQLite). Rolü ADIM 53'te **türetilmiş hafıza** ile kapandı. |
| `affaan-m/ECC` | ❌ | Ölçüt 4. **68 ajan + 286 skill**. **DÜZELTME:** plugin README'nin *"`ecc` npm'de yok"* cümlesi **BAYAT** — npm'de **`ecc-universal`** olarak yayımlanmış. Karar yine de değişmiyor (hacim + rolün kapanmış olması), ama gerekçe artık doğru olanıdır. |
| `openai/codex-plugin-cc` | ❌ | Ölçüt 1. Plugin (remote'ta kurulmaz) **ve** ChatGPT aboneliği / OpenAI API anahtarı ister. Kullanıcı bu hesabı bağlarsa **yeniden değerlendirilebilir** — çapraz-model review gerçek bir değer. |
| `alimirbagirzade/gstack` | ❌ | Ölçüt 2. Kullanıcının **kendi** deposu; 23+ rol komutu (`/review`, `/qa`, `/ship`) bu deponun `/session-start` → `/verify` → `/merge-check` → `/close-session` döngüsüyle örtüşür. Bun/Playwright/Supabase bağımlılıkları da ayrı bir yüzey. |
| `yt-dlp/yt-dlp` | ❌ | Skill/plugin/MCP **değil** — video indirici. Bu ürünle ilgisi yok. |
| `lyogavin/airllm` | ❌ | Skill/plugin/MCP **değil** — tek GPU'da büyük model koşturan Python kütüphanesi. Bu ürünle ilgisi yok. |
