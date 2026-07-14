// R6 / GAP-08 — Strategy Details package-graph structured model (doc 02
// §5.3 Position Entry Logic, §5.4 Position Exit Logic, §6). A TYPED OVERLAY on
// the free-form StrategyConfig draft payload that edits the two package-graph
// decision sections — the sections that PIN indicator / condition packages —
// so the Advanced (JSON) editor becomes a genuine fallback rather than the only
// way to compose them.
//
// Same discipline as lib/strategyForm.ts: enum VALUES mirror
// domain/strategy/config.py EXACTLY (the compiler parses with extra="forbid" at
// the top level); labels + ⓘ texts come VERBATIM from the V18 spec (doc 02 §6,
// HTML entities decoded, <br/> -> newlines). The client never validates
// strategy semantics — Validate / Save on the server remain the sole authority.
//
// extractGraphSections reads the current payload into form state, KEEPING each
// block's raw object so uncovered advanced fields (parameter_overrides,
// reference_package_ref, reference_timeframe, additional_reference_package_refs)
// survive a round-trip untouched. mergeGraphSections overlays the two covered
// sections back over the FULL payload, preserving every uncovered key.

import type { InfoPanelContent } from "@/lib/strategyForm";

// ---------------------------------------------------------------------------
// Enum option lists — VALUE mirrors config.py Literal members; LABEL is the
// V18 surface (doc 02 §5.3/§5.4). Required-no-default selects carry a leading
// "Choose…" empty option at the call site.
// ---------------------------------------------------------------------------

export interface SelectOption {
  value: string;
  label: string;
}

// PositionEntryLogic.direction_mode
export const DIRECTION_MODE_OPTIONS: SelectOption[] = [
  { value: "long", label: "Long" },
  { value: "short", label: "Short" },
  { value: "long_and_short", label: "Long & Short" },
];

// SignalBlock.rule (entry + exit share the four outer combination enums)
export const SIGNAL_RULE_OPTIONS: SelectOption[] = [
  { value: "required_indicator_blocks_only", label: "Required Indicator Blocks Only" },
  { value: "required_plus_any_supporting", label: "Required + Any Supporting Indicator Block" },
  {
    value: "required_plus_min_supporting",
    label: "Required + Minimum Supporting Indicator Blocks",
  },
  { value: "required_plus_all_confirmations", label: "Required + All Confirmations" },
];

// The signal rule value that reveals the min-supporting count field.
export const SIGNAL_MIN_SUPPORTING_RULE = "required_plus_min_supporting";

// IndicatorBlock.trigger_source
export const TRIGGER_SOURCE_OPTIONS: SelectOption[] = [
  { value: "indicator_native_trigger", label: "Indicator Native Trigger" },
  {
    value: "indicator_native_trigger_plus_condition",
    label: "Indicator Native Trigger + Condition Package",
  },
  { value: "indicator_output_plus_condition", label: "Indicator Output + Condition Package" },
];

// Trigger sources that make at least one active Condition Block mandatory
// (doc 02 §5.3 CANONICAL RULE — the server enforces it; the form only hints).
export const CONDITION_REQUIRING_TRIGGERS = new Set([
  "indicator_native_trigger_plus_condition",
  "indicator_output_plus_condition",
]);

// IndicatorBlock.direction (must fit the strategy direction mode; server validates)
export const BLOCK_DIRECTION_OPTIONS: SelectOption[] = [
  { value: "long", label: "Long" },
  { value: "short", label: "Short" },
  { value: "long_and_short", label: "Long & Short" },
];

// IndicatorBlock.timeframe / ReferenceLeg.timeframe / etc.
export const BLOCK_TIMEFRAME_OPTIONS: SelectOption[] = [
  { value: "same_as_base_tf", label: "Same as Base TF" },
  { value: "use_package_default_tf", label: "Use Package Default TF" },
  { value: "1m", label: "1m" },
  { value: "3m", label: "3m" },
  { value: "5m", label: "5m" },
  { value: "15m", label: "15m" },
  { value: "30m", label: "30m" },
  { value: "1h", label: "1h" },
  { value: "2h", label: "2h" },
  { value: "4h", label: "4h" },
  { value: "1D", label: "1D" },
];

// IndicatorBlock.validity
export const INDICATOR_VALIDITY_OPTIONS: SelectOption[] = [
  { value: "current_candle_only", label: "Current Candle Only" },
  { value: "1_candle", label: "1 Candle" },
  { value: "2_candles", label: "2 Candles" },
  { value: "3_candles", label: "3 Candles" },
  { value: "4_candles", label: "4 Candles" },
  { value: "until_opposite_signal", label: "Until Opposite Signal" },
];

// IndicatorBlock.requirement / ConditionBlock.requirement
export const REQUIREMENT_OPTIONS: SelectOption[] = [
  { value: "required", label: "Required" },
  { value: "supporting", label: "Supporting" },
];

// IndicatorBlock.condition_block_rule (nested condition aggregation)
export const CONDITION_BLOCK_RULE_OPTIONS: SelectOption[] = [
  { value: "required_condition_blocks_only", label: "Required Condition Blocks Only" },
  { value: "required_plus_any_supporting", label: "Required + Any Supporting" },
  { value: "required_plus_min_supporting", label: "Required + Minimum Supporting" },
  { value: "required_plus_all_supporting", label: "Required + All Supporting" },
];

export const CONDITION_MIN_SUPPORTING_RULE = "required_plus_min_supporting";

// ConditionBlock.validity — NOTE: no "4_candles" member (config.py contract).
export const CONDITION_VALIDITY_OPTIONS: SelectOption[] = [
  { value: "current_candle_only", label: "Current Candle Only" },
  { value: "1_candle", label: "1 Candle" },
  { value: "2_candles", label: "2 Candles" },
  { value: "3_candles", label: "3 Candles" },
  { value: "until_opposite_signal", label: "Until Opposite Condition" },
];

// PositionExitLogic.applies_to_direction
export const APPLIES_TO_OPTIONS: SelectOption[] = [
  { value: "long", label: "Long Positions" },
  { value: "short", label: "Short Positions" },
  { value: "long_and_short", label: "Long & Short Positions" },
];

// PositionExitLogic.partial_aftermath
export const PARTIAL_AFTERMATH_OPTIONS: SelectOption[] = [
  { value: "move_stop_to_entry", label: "Move Stop to Entry" },
  { value: "trailing_stop", label: "Activate Trailing Stop" },
  { value: "lock_in_profit", label: "Lock In Profit" },
  { value: "close_all", label: "Close Remaining at Next Exit Signal" },
];

// ---------------------------------------------------------------------------
// ⓘ panels — transcribed VERBATIM from doc 02 §6 (HTML entities decoded,
// <br/><br/> -> "\n\n"). Help-only: a panel never writes a form value.
// ---------------------------------------------------------------------------

export const STRATEGY_GRAPH_PANELS: Record<string, InfoPanelContent> = {
  positionEntryLogic: {
    title: "3. Position Entry Logic",
    body: "Bu bölüm, henüz pozisyon yokken hangi koşulların yeni bir işlem açacağını tanımlar. Yapı iki katmandan oluşur: Indicator Block bir indikatörün sinyal üretip üretmediğini değerlendirir; Signal Block birden fazla indikatörün birlikte giriş kararı üretip üretmeyeceğini değerlendirir.\n\nÖrnek: Reversal Sensor zorunlu olsun; Smoothed Heiken Ashi ve Volume Breakout supporting olsun. “Required + Minimum Supporting Indicator Blocks = 1” seçilirse Reversal Sensor doğru olmadan giriş olmaz; ayrıca supporting bloklardan en az biri de doğrulamalıdır.",
  },
  entrySignalBlock: {
    title: "Entry Signal Block",
    body: "Signal Block, giriş kararının en üst karar kutusudur. İçindeki Indicator Block’ları tek tek değerlendirir ve seçilen Indicator Rule’a göre nihai “pozisyon aç” sinyali üretir.\n\nBir indikatörün tek başına yeterli olmadığı stratejilerde, ana sinyali zorunlu tutup yardımcı sinyallerden belirli sayıda onay istemek için kullanılır.\n\nÖrnek: Ana dönüş göstergesi Required , hacim ve trend göstergeleri Supporting seçilebilir. Böylece sinyal sadece dönüş görüldüğü ve piyasa koşulu en az bir yardımcı göstergeden onay aldığı zaman üretilir.",
  },
  entryIndicatorRule: {
    title: "Entry Signal Block — Indicator Block Rule",
    body: "Bu açılır menü, Signal Block içindeki Required ve Supporting Indicator Block’ların nasıl birlikte karar vereceğini belirler.\n\n• Required Indicator Blocks Only: Yalnızca Required bloklar değerlendirilir; hepsi geçerliyse giriş sinyali oluşur. Supporting bloklar göz ardı edilir.\n\n• Required + Any Supporting Indicator Block: Tüm Required bloklar geçerli olmalı; buna ek olarak Supporting bloklardan birinin geçerli olması yeterlidir.\n\n• Required + Minimum Supporting Indicator Blocks: Tüm Required bloklar geçerli olmalı; ayrıca “Min. Supporting Indicator Blocks Count” alanında yazan sayı kadar Supporting blok geçerli olmalıdır.\n\n• Required + All Confirmations: Required ve Supporting olarak eklenen tüm blokların geçerli olması gerekir; en katı seçimdir.\n\nÖrnek: Bir Required ve üç Supporting blok var. Minimum sayı 2 seçilirse ana blok + yardımcı bloklardan ikisi doğru olduğunda giriş sinyali oluşur.",
  },
  entryMinSupportingIndicatorCount: {
    title: "Signal Block — Min. Supporting Indicator Blocks Count",
    body: "Bu sayı, Signal Block içindeki Supporting Indicator Block ’lardan kaç tanesinin giriş kararını onaylaması gerektiğini belirler. Yalnızca Indicator Rule içinde Required + Minimum Supporting Indicator Blocks seçildiğinde anlamlıdır.\n\nBu alan, bir Indicator Block’un içindeki condition sayısını değil, birbirinden ayrı indikatör bloklarının onay sayısını kontrol eder.\n\nÖrnek: Reversal Sensor Required ; RSI, Volume Breakout ve Smoothed Heiken Ashi Supporting olsun. Count = 2 seçilirse, Reversal Sensor doğru olduktan sonra üç yardımcı indikatörden en az ikisinin de doğru olması gerekir.",
  },
  entryIndicatorBlock: {
    title: "Indicator Block",
    body: "Indicator Block, tek bir Indicator Package’ın bu stratejide nasıl kullanılacağını tanımlar. İçindeki Condition Block’lar, indikatörün hangi davranışının geçerli giriş sinyali sayılacağını belirler.\n\nYeni bir indikatör eklemek, stratejiye yeni bir onay veya zorunlu şart eklemek demektir; aynı indikatörü farklı timeframe veya farklı koşulla ayrı bir block olarak da ekleyebilirsin.\n\nÖrnek: Smoothed Heiken Ashi seçilir; koşul olarak “Color Turns Green” atanır; Requirement “Supporting” yapılır. Bu block, ana giriş sinyalini tek başına başlatmaz fakat onaylayabilir.",
  },
  indicatorValidity: {
    title: "Indicator Block — Validity",
    body: "İndikatörün ürettiği geçerli sinyalin kaç mum boyunca kullanılabilir sayılacağını belirler. Bu, farklı indikatörlerin tam aynı mumda sinyal vermek zorunda kalmasını engelleyebilir; fakat süre uzadıkça eski sinyalle işlem açma riski artar.\n\n• Current Candle Only: Sinyal yalnızca oluştuğu mumda kullanılabilir.\n\n• 1 / 2 / 3 / 4 Candles: Sinyal belirtilen mum süresince aktif kabul edilir.\n\n• Until Opposite Signal: Ters bir sinyal oluşana kadar aktif kalır.\n\nÖrnek: 15 dakikalık timeframe’de 3 Candles, sinyalin oluşmasından sonra en fazla 45 dakika giriş kararına katkı verebilmesi anlamına gelir.",
  },
  indicatorRequirement: {
    title: "Indicator Block — Requirement",
    body: "Bu block’un nihai giriş kararındaki statüsünü belirler.\n\n• Required: Bu block geçerli sinyal üretmeden Signal Block giriş sinyali üretemez. Ana koşullar için kullanılır.\n\n• Supporting: Bu block yardımcı onaydır. Gerekip gerekmediğini Signal Block içindeki Indicator Rule ve minimum supporting sayısı belirler.\n\nÖrnek: Reversal Sensor giriş fikrinin kaynağıysa Required; hacim yeterliliği yalnızca onaysa Volume Breakout Supporting seçilebilir.",
  },
  conditionRule: {
    title: "Indicator Block — Condition Block Rule",
    body: "Bir Indicator Block içine birden fazla Condition Block eklenebilir. Bu menü, o koşulların indikatör sinyalini üretmek için nasıl birleşeceğini belirler.\n\n• Required Condition Blocks Only: Required olarak işaretlenen tüm koşullar doğru olmalıdır; Supporting koşullar sonuca katılmaz.\n\n• Required + Any Supporting Condition Block: Required koşulların tamamına ek olarak en az bir Supporting koşul doğru olmalıdır.\n\n• Required + Minimum Supporting Condition Blocks: Required koşulların tamamına ek olarak belirlenen sayıda Supporting koşul doğru olmalıdır.\n\n• Required + All Supporting Conditions: Eklenen tüm Required ve Supporting koşullar doğru olmalıdır.\n\nÖrnek: Heiken Ashi “yeşile döndü” Required, “iki mum yeşil devam etti” Supporting ise, ikinci şartı onay olarak kullanıp kullanmayacağını bu menü belirler.",
  },
  entryMinSupportingConditionCount: {
    title: "Indicator Block — Min. Supporting Condition Blocks Count",
    body: "Bu sayı, yalnızca içinde bulunduğu Indicator Block ’a eklenmiş Supporting Condition Block’lardan kaçının aynı indikatörün sinyalini onaylaması gerektiğini belirler. Signal Block seviyesindeki indicator sayımıyla karıştırılmamalıdır.\n\nÖrnek: RSI Indicator Block içinde “Crosses Above 30” Required; “Bullish Divergence” ve “Slope Turns Up” Supporting olsun. Count = 1 seçilirse Required koşula ek olarak bu iki supporting koşuldan biri geçerli olduğunda RSI block sinyal üretir.",
  },
  entryConditionBlock: {
    title: "Condition Block",
    body: "Condition Block, üstündeki Indicator Package’ın hangi somut davranışının “true” kabul edileceğini seçtiğin yerdir. Bir Indicator Block’a birden fazla condition ekleyerek daha dar veya daha onaylı bir sinyal tarif edebilirsin.\n\nÖrnek: RSI indicator için “Crosses Above 30” koşulu, RSI’ın yalnızca düşük olduğunu değil, düşük bölgeden yukarı doğru çıktığını ifade eder; bu daha somut bir giriş davranışıdır.",
  },
  conditionRequirement: {
    title: "Condition Block — Requirement",
    body: "Bu koşulun bağlı bulunduğu Indicator Block içinde zorunlu mu yoksa yardımcı mı olacağını belirler.\n\n• Required: Condition true olmadan Indicator Block geçerli sinyal üretemez.\n\n• Supporting: Condition bir onay olarak değerlendirilir; gerekli sayıya ulaşılıp ulaşılmadığı Condition Rule tarafından belirlenir.\n\nÖrnek: “Fiyat desteğe yakın” Required, “hacim ortalamanın üzerinde” Supporting olabilir.",
  },
  conditionValidity: {
    title: "Condition Block — Validity",
    body: "Koşul true olduktan sonra kaç mum boyunca hâlâ geçerli sayılacağını belirler.\n\n• Current Candle Only: Koşul sadece oluştuğu mumda kullanılabilir.\n\n• 1 / 2 / 3 / 4 Candles: Koşul belirlenen mum sayısı süresince true olarak taşınır.\n\n• Until Opposite Condition: Karşıt bir condition oluşana kadar geçerli kalır.\n\nÖrnek: Fiyat desteğe dokunduğu mumdan sonra dönüş göstergesi iki mum sonra oluşabiliyorsa, destek koşuluna 2 Candles validity verilebilir.",
  },
  positionExitLogic: {
    title: "4. Position Exit Logic",
    body: "Bu bölüm, açık bir pozisyonun normal strateji kararıyla nasıl yönetileceğini belirler. Stop bölümünden farkı şudur: exit, kâr alma veya strateji sinyalinin bittiğini görme gibi planlı çıkış davranışlarını tanımlar; stop ise risk korumasıdır.\n\nÖrnek: Long pozisyonda fiyat direnç bölgesine ulaştığında %50 kapatıp kalan pozisyonu trailing stop ile yönetmek, Position Exit Logic içinde tarif edilir.",
  },
  exitSignalBlock: {
    title: "Exit Signal Block",
    body: "Açık pozisyonda hangi indicator onaylarının bir exit eylemi oluşturacağını belirleyen üst bloktur. Önce hangi pozisyona uygulanacağını ve oluştuğunda ne yapılacağını seçersin; ardından Indicator Block’larla çıkış koşulunu kurarsın.\n\nÖrnek: Bu blok yalnızca long pozisyonlara uygulanabilir ve “Close 50%” eylemiyle, long trend zayıflayınca pozisyonun yarısını kapatabilir.",
  },
  appliesToPosition: {
    title: "Applies To Position",
    body: "Exit Signal Block’un hangi açık pozisyon türünde değerlendirileceğini belirler.\n\n• Long Positions: Yalnızca alış yönünde açık pozisyon varsa bu exit kuralı çalışır.\n\n• Short Positions: Yalnızca satış yönünde açık pozisyon varsa çalışır.\n\n• Long & Short Positions: Aynı çıkış yapısı her iki yön için de değerlendirilebilir; seçilen condition’ın yönle uyumlu kurulması gerekir.\n\nÖrnek: “Price Near Resistance” long pozisyon için kâr alma nedeni olabilir; short pozisyon için aynı koşul genellikle çıkış nedeni olmaz.",
  },
  exitAction: {
    title: "Exit Action",
    body: "Geçerli exit sinyali oluştuğu anda açık pozisyona uygulanacak işlemdir.\n\n• Close 100%: İlgili pozisyon tamamen kapatılır.\n\n• Close 75% / 50% / 25%: Pozisyonun yalnızca belirtilen bölümü kapanır; kalan kısmın yönetimi After Partial Close ile belirlenir.\n\n• Move Stop to Entry: Pozisyon kapanmaz; stop giriş fiyatına taşınarak artık başlangıç sermayesi korunmaya çalışılır.\n\n• Activate Trailing Stop: Pozisyon kapanmaz; fiyat kâra devam ederse takip edilir, geri dönerse kapanır.\n\n• Block New Scaling: Pozisyon açık kalır fakat yeni layer eklenemez.\n\n• Exit Warning Only: Eylem uygulanmaz; sinyal yalnızca kaydedilir.\n\nÖrnek: İlk hedefe ulaşıldığında Close 50% seçip kalan yarıyı trailing ile taşımak mümkündür.",
  },
  afterPartialClose: {
    title: "After Partial Close",
    body: "Exit Action pozisyonun tamamını değil bir kısmını kapatıyorsa, açık kalan miktarın bundan sonra nasıl yönetileceğini belirler.\n\n• Continue With Existing Exit / Stop Rules: Kalan pozisyon aynı kurallarla izlenmeye devam eder.\n\n• Move Stop to Entry: Kalan miktarın stop seviyesi ilk giriş fiyatına taşınır.\n\n• Activate Trailing Stop: Kalan miktar fiyatı takip eden stop ile yönetilir.\n\n• Close Remaining Position at Next Exit Signal: Sonraki geçerli exit sinyalinde geri kalan bölüm tamamen kapatılır.\n\n• Block New Scaling: Kalan pozisyon açık kalır fakat ek kademe açılmaz.\n\nÖrnek: Pozisyonun %50’si hedefte kapandıktan sonra Move Stop to Entry seçilirse kalan %50’nin zarara dönüşmesi engellenmeye çalışılır.",
  },
  exitIndicatorRule: {
    title: "Exit Signal Block — Indicator Block Rule",
    body: "Exit kararında Required ve Supporting Indicator Block’ların nasıl birleşeceğini belirler.\n\n• Required Indicator Blocks Only: Yalnızca Required blokların tamamı exit sinyali üretirse eylem uygulanır.\n\n• Required + Any Supporting Indicator Block: Required bloklara ek olarak herhangi bir supporting çıkış onayı yeterlidir.\n\n• Required + Minimum Supporting Indicator Blocks: Required bloklara ek olarak belirtilen sayıda supporting onay gereklidir.\n\n• Required + All Confirmations: Eklenen bütün bloklar çıkışı onaylamalıdır.\n\nÖrnek: Dirence ulaşma Required, Heiken Ashi’nin kırmızıya dönmesi Supporting ise, minimum sayı 1 seçildiğinde ancak ikisi birlikte görülürse kısmi çıkış yapılır.",
  },
  exitIndicatorBlock: {
    title: "Exit — Indicator Block",
    body: "Tek bir indikatörün açık pozisyondan çıkış kararına nasıl katkı vereceğini tanımlar. Seçtiğin Condition Block’lar bu indikatörün hangi davranışının exit sinyali olduğunu belirler.\n\nÖrnek: Predictive Ranges indicator’ı içinde “Price Near Resistance” condition’ı, long pozisyonda bir exit onayı olarak kullanılabilir.",
  },
  exitRequirement: {
    title: "Exit Indicator Block — Requirement",
    body: "• Required: Bu Indicator Block geçerli çıkış sinyali üretmeden Signal Block’un exit eylemi çalışmaz.\n\n• Supporting: Bu blok yardımcı çıkış onayıdır; gerekli olup olmadığını Indicator Rule belirler.\n\nÖrnek: Hedef bölgeye erişim Required; momentum zayıflaması Supporting olarak seçilebilir.",
  },
  exitConditionBlock: {
    title: "Exit — Condition Block",
    body: "Bağlı olduğu indicator’ın hangi somut davranışının çıkış açısından true sayılacağını belirler. Bu bloklar yeni eklenebildiği için, bir indikatör için birden fazla çıkış şartı kurabilirsin.\n\nÖrnek: Smoothed Heiken Ashi için “Color Turns Red”, açık long pozisyonun zayıfladığını gösteren çıkış koşulu olabilir.",
  },
  exitConditionRequirement: {
    title: "Exit Condition — Requirement",
    body: "• Required: Bu condition doğru olmadan üst Indicator Block çıkış sinyali üretemez.\n\n• Supporting: Bu condition yardımcıdır; Condition Rule’un istediği sayıda yardımcı koşuldan biri olabilir.\n\nÖrnek: “Resistance Reached” Required, “RSI Bearish Divergence” Supporting olarak kurulabilir.",
  },
  exitConditionValidity: {
    title: "Exit Condition — Validity",
    body: "Exit koşulu oluştuktan sonra kaç mum boyunca kullanılabilir sayılacağını belirler.\n\n• Current Candle Only: Çıkış koşulu yalnızca görüldüğü mumda geçerlidir.\n\n• 1 / 2 / 3 / 4 Candles: Koşul belirtilen süre boyunca aktif kalır.\n\n• Until Opposite Condition: Karşıt koşul gelene kadar geçerli sayılır.\n\nÖrnek: Fiyat hedefe ulaştı fakat ikinci onay bir mum sonra geliyorsa validity 1 Candle seçimi bu iki koşulun birlikte exit üretmesine izin verebilir.",
  },
  logicBasedStopBlock: {
    title: "Logic-Based Stop Block",
    body: "Bir indikatör ve ona bağlı condition’lar üzerinden stop sinyali üretir. Fiyat önceden belirlenmiş yüzde stop seviyesine gelmeden önce, stratejinin temel mantığı bozulduysa pozisyonu kapatmak için kullanılır.\n\n+ Add Condition , aynı indikatör için yeni bir koşul ekler. + Add Logic-Based Stop Block , farklı bir indikatörle ayrı bir stop kuralı kurar.\n\nÖrnek: Long pozisyon için Smoothed Heiken Ashi seçip “Color Turns Red” condition’ı eklenirse, gösterge kırmızıya döndüğünde stop sinyali üretilebilir.",
  },
};

// ---------------------------------------------------------------------------
// Form state — a structured mirror. Each block keeps its ORIGINAL raw dict so
// uncovered advanced fields survive a round-trip. New blocks carry raw = {}.
// ---------------------------------------------------------------------------

export interface PackageRefForm {
  package_root_id: string;
  package_revision_id: string;
  package_content_hash: string;
}

export interface ConditionBlockForm {
  key: string;
  condition_block_id: string;
  enabled: boolean;
  package_ref: PackageRefForm | null;
  requirement: string;
  validity: string;
  raw: Record<string, unknown>;
}

export interface IndicatorBlockForm {
  key: string;
  block_id: string;
  enabled: boolean;
  package_ref: PackageRefForm | null;
  trigger_source: string;
  direction: string;
  timeframe: string;
  validity: string;
  requirement: string;
  condition_block_rule: string;
  min_supporting_condition_count: string;
  conditions: ConditionBlockForm[];
  raw: Record<string, unknown>;
}

export interface EntryLogicForm {
  direction_mode: string;
  signal_rule: string;
  signal_min_supporting_count: string;
  blocks: IndicatorBlockForm[];
  raw: Record<string, unknown>;
}

export interface ExitLogicForm {
  active: boolean;
  applies_to_direction: string;
  close_percentage: string;
  partial_aftermath: string;
  signal_rule: string;
  signal_min_supporting_count: string;
  blocks: IndicatorBlockForm[];
  raw: Record<string, unknown>;
}

export interface StrategyGraphForm {
  entry: EntryLogicForm;
  exit: ExitLogicForm;
}

// ---------------------------------------------------------------------------
// Coercion helpers
// ---------------------------------------------------------------------------

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function str(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

function bool(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function enumStr(value: unknown, fallback: string): string {
  return typeof value === "string" && value !== "" ? value : fallback;
}

// Generate a stable client id for a NEW block (any string is a legal id in the
// config.py contract; the server never re-derives it).
export function newBlockId(): string {
  return crypto.randomUUID();
}

function extractPackageRef(value: unknown): PackageRefForm | null {
  const ref = asRecord(value);
  const rootId = str(ref.package_root_id);
  const revisionId = str(ref.package_revision_id);
  const contentHash = str(ref.package_content_hash);
  if (rootId === "" && revisionId === "" && contentHash === "") return null;
  return {
    package_root_id: rootId,
    package_revision_id: revisionId,
    package_content_hash: contentHash,
  };
}

function extractCondition(raw: unknown, index: number): ConditionBlockForm {
  const c = asRecord(raw);
  const id = str(c.condition_block_id) || newBlockId();
  return {
    key: id || `cond-${index}`,
    condition_block_id: id,
    enabled: bool(c.enabled, true),
    package_ref: extractPackageRef(c.package_ref),
    requirement: str(c.requirement),
    validity: enumStr(c.validity, "3_candles"),
    raw: c,
  };
}

function extractBlock(raw: unknown, index: number): IndicatorBlockForm {
  const b = asRecord(raw);
  const id = str(b.block_id) || newBlockId();
  return {
    key: id || `block-${index}`,
    block_id: id,
    enabled: bool(b.enabled, true),
    package_ref: extractPackageRef(b.package_ref),
    trigger_source: str(b.trigger_source),
    direction: enumStr(b.direction, "long_and_short"),
    timeframe: enumStr(b.timeframe, "same_as_base_tf"),
    validity: enumStr(b.validity, "3_candles"),
    requirement: str(b.requirement),
    condition_block_rule: str(b.condition_block_rule),
    min_supporting_condition_count: str(b.min_supporting_condition_count),
    conditions: asArray(b.condition_blocks).map((c, i) => extractCondition(c, i)),
    raw: b,
  };
}

function newBlock(): IndicatorBlockForm {
  const id = newBlockId();
  return {
    key: id,
    block_id: id,
    enabled: true,
    package_ref: null,
    trigger_source: "",
    direction: "long_and_short",
    timeframe: "same_as_base_tf",
    validity: "3_candles",
    requirement: "required",
    condition_block_rule: "",
    min_supporting_condition_count: "",
    conditions: [],
    raw: {},
  };
}

export function newCondition(): ConditionBlockForm {
  const id = newBlockId();
  return {
    key: id,
    condition_block_id: id,
    enabled: true,
    package_ref: null,
    requirement: "required",
    validity: "3_candles",
    raw: {},
  };
}

export { newBlock };

export function extractGraphSections(payload: Record<string, unknown>): StrategyGraphForm {
  const entry = asRecord(payload.position_entry_logic);
  const entrySignal = asRecord(entry.signal_block);
  const entryBlocks = asArray(entry.indicator_blocks).map((b, i) => extractBlock(b, i));

  const exit = asRecord(payload.position_exit_logic);
  const exitSignal = asRecord(exit.signal_block);
  const rawExitBlocks = exit.indicator_blocks;
  const exitBlocks = asArray(rawExitBlocks).map((b, i) => extractBlock(b, i));
  const exitActive = Array.isArray(rawExitBlocks) && exitBlocks.length > 0;

  return {
    entry: {
      direction_mode: enumStr(entry.direction_mode, "long_and_short"),
      signal_rule: str(entrySignal.rule),
      signal_min_supporting_count: str(entrySignal.min_supporting_count),
      blocks: entryBlocks.length > 0 ? entryBlocks : [newBlock()],
      raw: entry,
    },
    exit: {
      active: exitActive,
      applies_to_direction: enumStr(exit.applies_to_direction, "long_and_short"),
      close_percentage: str(exit.close_percentage) || "100",
      partial_aftermath: enumStr(exit.partial_aftermath, "move_stop_to_entry"),
      signal_rule: str(exitSignal.rule),
      signal_min_supporting_count: str(exitSignal.min_supporting_count),
      blocks: exitBlocks,
      raw: exit,
    },
  };
}

// ---------------------------------------------------------------------------
// Merge — overlay the two covered sections back onto the FULL payload.
// ---------------------------------------------------------------------------

function decOrOmit(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

function intOrOmit(value: string): number | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isNaN(parsed) ? undefined : parsed;
}

// Set covered keys on a raw-derived object; DELETE a key whose form value is
// empty so an omitted required field surfaces "field required" on the server
// and a defaulted field takes its default (the server decides, never the form).
function setOrDelete(out: Record<string, unknown>, key: string, value: unknown): void {
  if (value === undefined || value === "") delete out[key];
  else out[key] = value;
}

function mergeCondition(c: ConditionBlockForm, index: number): Record<string, unknown> {
  const out: Record<string, unknown> = { ...c.raw };
  out.condition_block_id = c.condition_block_id;
  out.display_order = index;
  out.enabled = c.enabled;
  setOrDelete(out, "requirement", c.requirement);
  setOrDelete(out, "validity", c.validity);
  if (c.package_ref) out.package_ref = { ...c.package_ref };
  else delete out.package_ref;
  return out;
}

function mergeBlock(b: IndicatorBlockForm, index: number): Record<string, unknown> {
  const out: Record<string, unknown> = { ...b.raw };
  out.block_id = b.block_id;
  out.display_order = index;
  out.enabled = b.enabled;
  if (b.package_ref) out.package_ref = { ...b.package_ref };
  else delete out.package_ref;
  setOrDelete(out, "trigger_source", b.trigger_source);
  setOrDelete(out, "direction", b.direction);
  setOrDelete(out, "timeframe", b.timeframe);
  setOrDelete(out, "validity", b.validity);
  setOrDelete(out, "requirement", b.requirement);
  setOrDelete(out, "condition_block_rule", b.condition_block_rule);
  setOrDelete(out, "min_supporting_condition_count", intOrOmit(b.min_supporting_condition_count));
  if (b.conditions.length > 0) {
    out.condition_blocks = b.conditions.map((c, i) => mergeCondition(c, i));
  } else {
    delete out.condition_blocks;
  }
  return out;
}

function mergeSignalBlock(rule: string, minCount: string): Record<string, unknown> | undefined {
  if (rule === "") return undefined;
  const out: Record<string, unknown> = { rule };
  const min = intOrOmit(minCount);
  if (rule === SIGNAL_MIN_SUPPORTING_RULE && min !== undefined) {
    out.min_supporting_count = min;
  }
  return out;
}

export function mergeGraphSections(
  payload: Record<string, unknown>,
  form: StrategyGraphForm,
): Record<string, unknown> {
  const e = form.entry;
  const entry: Record<string, unknown> = { ...e.raw };
  setOrDelete(entry, "direction_mode", e.direction_mode);
  const entrySignal = mergeSignalBlock(e.signal_rule, e.signal_min_supporting_count);
  if (entrySignal) entry.signal_block = entrySignal;
  else delete entry.signal_block;
  entry.indicator_blocks = e.blocks.map((b, i) => mergeBlock(b, i));

  const x = form.exit;
  const exit: Record<string, unknown> = { ...x.raw };
  setOrDelete(exit, "applies_to_direction", x.applies_to_direction);
  setOrDelete(exit, "close_percentage", decOrOmit(x.close_percentage));
  setOrDelete(exit, "partial_aftermath", x.partial_aftermath);
  if (x.active && x.blocks.length > 0) {
    exit.indicator_blocks = x.blocks.map((b, i) => mergeBlock(b, i));
    const exitSignal = mergeSignalBlock(x.signal_rule, x.signal_min_supporting_count);
    if (exitSignal) exit.signal_block = exitSignal;
    else delete exit.signal_block;
  } else {
    // Inactive exit placeholder (doc 02 §5.4): no active exit node.
    delete exit.indicator_blocks;
    delete exit.signal_block;
  }

  return {
    ...payload,
    position_entry_logic: entry,
    position_exit_logic: exit,
  };
}
