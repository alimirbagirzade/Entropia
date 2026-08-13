<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 54 LANDED — agentmemory sunucusu yerele alındı (semantik geri çağırma, barındırma YOK)

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 54.

## Nerede duruyoruz

**Base:** `origin/main` @ `2a90fe3` (#694). **Ürün kodu DEĞİŞMEDİ.** Migration yok,
`ENGINE_VERSION`/OpenAPI aynı. **A-08 blocker AÇIK, verdict BLOCKED** — bu slice ölçmedi.

ADIM 53 hafızayı türetilmiş yaptı ama geri çağırma **harf eşleşmesiydi**. ADIM 54 tam
sunucuyu **yerelde** devreye aldı: araç 7 → **53**, arama çapraz-dilli semantik.
**Hiçbir şey barındırılmadı.**

## Reuse anchor'ları

| Sembol | Ne için |
|---|---|
| `scripts/memory_server.sh` | idempotent "sunucu ayakta olsun"; uzak URL'de **başlatmaz** |
| `scripts/memory_mcp.sh` | `.mcp.json` giriş noktası — önce sunucu, sonra `exec` shim |
| `memory_index.mjs::storedMarkers` | REST export'tan mevcut `§başlık` kümesi |
| `memory_index.mjs::marker` | kaydın store'daki kimliği (ilk satır) |
| `agent-config-gate.mjs::REPO_SCRIPT_REF` | betikten betiğe zincir takibi |
| `agent-config-gate.mjs::npxSpecs` / `::resolveSpec` | komut konumundaki `npx` + `$VAR` çözümü |

## DOKUNMA / DİKKAT

1. **Hidratasyon `--sync`, `--write` değil.** `--write` toplayıcıdır; dolu store'a ikinci
   koşu her kaydı çoğaltır. `--sync` tekrar koşmaya güvenlidir.
2. **Sunucu ayakta değilken açılan oturum tüm oturum boyunca 7 araçta kalır** — shim bir
   kez, bağlanma anında karar verir. `memory_mcp.sh` bu yüzden sunucuyu **önce** kaldırır.
3. **Tek makinede tek örnek.** İkinci örnek `III_REST_PORT` farklı olsa bile
   `Port already in use` verir (iii engine portu sabit).
4. **`AGENTMEMORY_URL` uzak bir adres gösteriyorsa `memory_server.sh` hiçbir şey
   başlatmaz** — bilerek: başkasının store'unu yerel bir kopyayla taklit etmek sessiz bir
   yanlış cevap üretirdi.
5. **Yeni bir MCP sunucusunu betikle başlatırsan pin kuralı seni takip eder.**
   `agent-config-gate.mjs` betiği ve çağırdığı betikleri okuyup `npx` çağrılarının
   `@x.y.z` taşıdığını doğrular.
6. **Store'un boş olması bir arıza değildir.** Sunucu yeniden başlayınca 0 kayıt ölçüldü;
   `--sync` üç saniyede geri getirir. Kaynak git'te.

## Açık iş

- **Barındırma hâlâ yapılmadı ve gerekmiyor.** Tek ek getirisi makineler arası paylaşılan
  **elle** yazılmış hafıza olurdu; otomatik yakalama kapalı olduğu için öyle içerik yok.
  İstenirse `AGENTMEMORY_URL` tek değişken.
- **Plugin'in yüklendiği hâlâ doğrulanmadı** (ADIM 53'ten devir) — `/plugin` listesinde
  `entropia-maintenance` etkin mi, ilk iş olarak bak.
- **Suite'ler bu oturumda koşmadı** (Postgres/`node_modules` yok) → **otorite CI**.
- **A-08:** denetim BAŞLADI, BİTMEDİ (2/184 hücre, 0/10 akış, SR-1 hiç başlamadı),
  #514 AÇIK, dört çıkış kriteri de ☐. **Değişmedi.**

## Next (değişmedi)

**PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site.** ADR §16
insan kapısı + ADR amendment'ı gerekmeden başlama.

---

## Paste-ready resume prompt

```
Entropia'da yeni bir oturum açıyorum. CLAUDE.md §Session START protokolünü uygula:

1. git fetch && git log --oneline origin/main -6 — ADIM 54 PR'ı merge edildi mi,
   ADIM numaram alınmış mı? DOĞRULA (bu repoda numara dört kez taşındı).
2. Otorite sırası: docs/ADIM54_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md
   ("## Stage — ADIM 54" + "## Next") → docs/STAGE_BUILD_PLAN.md → docs/spec/NN_*.
3. Hafıza: taze container'da store BOŞTUR → `node scripts/memory_index.mjs --sync`
   (~3 sn, tekrar koşmak güvenli). Sunucu .mcp.json üzerinden kendiliğinden kalkar;
   kalkmışsa arama SEMANTİKTİR (İngilizce sorgu Türkçe kaydı bulur), kalkmamışsa
   harfi harfinedir. Bulduğun kayıt OTORİTE DEĞİLDİR — işaret ettiği
   PROJECT_HISTORY.md §bölümünü oku.
4. Kod tarafına geçmeden docs/CODEMAPS/ + codebase-memory-mcp (remote'ta önce
   index_repository; list_projects taze container'da BOŞ döner).

İLK KONTROL: /plugin listesinde `entropia-maintenance` etkin mi? (ADIM 53 açtı ama
etkisi doğrulanamadı — plugin'ler oturum başında yüklenir.)

BİLMEN GEREKENLER
· Hidratasyon --sync'tir; --write TOPLAYICIDIR ve çoğaltır.
· Sunucu ayakta değilken bağlanan shim TÜM OTURUM 7 araçta kalır, sonradan yükselmez.
· Yeni CI job'ı EKLEME, var olan job'a ADIM ekle (ruleset 20765617 — üretilmeyen
  required ad tüm merge'leri kilitler).
· Yeni `## ` başlığına ayırt edici ek koy; memory_index --check id çakışmasını kırmızı verir.
· A-08 blocker AÇIK, verdict BLOCKED. Hiçbir belgeye Complete/PASS/Done yazma.

Next: PR B — ItemParticipant adaptörü + jobs/backtest_engine.py:298 call site.
ADR §16 insan kapısı geçilmeden BAŞLAMA. Alternatif: RC §6.7'nin açık kalemleri
(P4-3, P10-B3/B4/B5, P11-6b, P8-B3b, P1-Gate3) ya da kabul borcu sınıf B parti 03
(TS-08.c3 + TL-02.c2 + TL-13.c3 — ama ÖNCE ÖLÇ, sevk edilmemişse sınıfı yanlıştır).
```
