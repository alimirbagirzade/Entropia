// GAP-08 — Strategy Details structured form model + ⓘ Information Content
// Catalog (doc 02 §5.2/§5.5/§5.6/§5.9 + §6). A TYPED OVERLAY on the free-form
// StrategyConfig draft payload: the structured form edits the flat
// (package-picker-free) sections — Data & Execution, Protection / Stop Logic,
// Position Sizing, Conflict / Position Handling. The package-graph sections that
// PIN packages — Position Entry / Exit Logic — moved to a structured editor in
// R6 (lib/strategyGraph.ts + StrategyGraphForm); Scaling and Restrictions stay
// in the retained Advanced (JSON) editor. extractFlatSections reads the current
// payload into form state; mergeFlatSections writes the covered sections back
// over the FULL payload, preserving every uncovered key (the compiler parses
// the whole payload with extra="forbid", so nothing may be dropped). Enum
// VALUES mirror domain/strategy/config.py exactly; the labels + ⓘ texts come
// from the V18 spec (doc 02). The client never validates strategy semantics —
// Validate / Save on the server remain the sole authority (issues rendered
// verbatim).

export interface InfoPanelContent {
  title: string;
  body: string;
}

// ⓘ panels for the flat sections, transcribed VERBATIM from doc 02 §6
// (HTML entities decoded, <br/> → newlines). The graph-section panels
// (Condition/Indicator/Exit blocks, Scaling, Restrictions) land with those
// sections in the follow-up slice.
export const STRATEGY_INFO_PANELS: Record<string, InfoPanelContent> = {
  orderType: {
    title: "Order Type",
    body: "Bu seçim, sinyal oluştuğunda backtest motorunun pozisyona nasıl girmiş sayacağını belirler. Emir türü, giriş fiyatını, işlem sayısını ve slippage etkisini doğrudan değiştirebilir.\n\n• Market Order: Sinyal geldiğinde pozisyon piyasa fiyatından hemen açılmış kabul edilir. En basit ve en hızlı dolum varsayımıdır; spread ve slippage etkisi ayrıca uygulanabilir.\n\n• Limit Order: Emir sadece belirlenen limit fiyatına gelinirse dolmuş sayılır. Daha iyi fiyat hedeflenir ama fiyat oraya gelmezse işlem kaçabilir.\n\n• Stop Order: Fiyat belirlenen tetik seviyesine ulaşınca emir aktive olur ve genellikle market davranışına yakın şekilde işleme girer. Breakout veya momentum girişlerinde kullanılabilir.\n\n• Stop-Limit Order: Önce stop seviyesi tetiklenir, sonra limit fiyat koşulu aranır. Tetik oluşsa bile limit fiyat dolmazsa pozisyon açılmayabilir.\n\n• Simulation Only: Gerçek emir tipi gibi davranmaz; sinyalin pozisyon açma mantığını basitleştirilmiş sanal dolumla test etmek için kullanılır.\n\nÖrnek: Long sinyali 100 seviyesinde geldi. Market Order seçilirse işlem 100 civarında hemen açılır. Limit Order seçilirse sistem örneğin 99.50 seviyesine geri çekilme bekleyebilir. Fiyat 99.50'ye inmezse işlem gerçekleşmez.",
  },
  limitOrderDetails: {
    title: "Limit Order Details",
    body: "Limit emir, \"şu fiyattan veya daha iyi fiyattan işlem aç\" talimatıdır. Backtest, limit emri gerçekten kullanılabilir biçimde simüle edecekse sadece sinyalin oluştuğunu bilmek yetmez; fiyatın nasıl yerleştirileceğini, ne kadar süre bekleneceğini, dolmazsa ne yapılacağını ve kısmi dolumun kabul edilip edilmeyeceğini de bilmelidir.\n\nÖrnek: Long sinyali 100 fiyatta oluştu. Limit fiyat 99.50 seçilmişse, fiyat bu seviyeye geri gelmeden pozisyon açılmış kabul edilmemelidir.",
  },
  limitPriceRule: {
    title: "Limit Price Rule",
    body: "Bu seçim, sinyal oluştuktan sonra limit emrin hangi fiyata yazılacağını belirler. Fiyat seçimi, işlem sayısını ve görünen performansı doğrudan değiştirebilir.\n\n• Entry signal price: Emir, sinyalin hesaplandığı fiyat seviyesine konur. Örneğin sinyal 100'de oluştuysa limit 100 olur.\n\n• Best bid / ask: O anda piyasada görülen en yakın alınabilir/satılabilir fiyat kullanılır. İşlem gerçekleşme ihtimali daha yüksektir; ancak spread etkisini taşır.\n\n• Signal price minus offset: Limit fiyat sinyal fiyatından daha aşağıya konur. Long işlemde daha ucuz giriş beklenir; fiyat geri gelmezse işlem kaçabilir.\n\n• Signal price plus offset: Emir daha kolay dolabilecek tarafa yaklaştırılır. Dolum ihtimali artar fakat daha kötü fiyattan işlem açılabilir.\n\nÖrnek: Long sinyali 100, offset %0.5 ise Signal price minus offset seçimi 99.50'de alış bekler.",
  },
  orderValidity: {
    title: "Order Validity",
    body: "Limit emir hemen dolmak zorunda değildir. Bu alan, emir dolmadan bekleyebileceği süreyi belirler. Süre dolunca emir artık o sinyale ait geçerli bir giriş sayılmaz.\n\n• Current candle only: Fiyat aynı mum içinde limite dokunmazsa işlem iptal edilir.\n\n• 1 candle: Emir bir sonraki mum boyunca da dolabilir; sonrasında iptal edilir.\n\n• 3 candles: Emir üç mum boyunca bekler. Daha fazla dolum olabilir ancak eski bir sinyalle geç giriş riski artar.\n\n• 4 candles: Daha uzun bekleme süresidir; özellikle yavaş stratejiler için kullanılabilir.\n\n• Until cancelled: Başka bir iptal kuralı çalışana kadar emir açık kabul edilir.\n\nÖrnek: 15 dakikalık veride \"3 candles\", limit emrin en fazla 45 dakika bekleyebilmesi anlamına gelir.",
  },
  ifNotFilled: {
    title: "If Not Filled",
    body: "Limit emir seçilmiş fiyata hiç ulaşmazsa sistemin ne yapacağını belirler. Bu karar verilmezse backtest dolmayan işlemleri yanlışlıkla gerçekleşmiş sayabilir.\n\n• Cancel Order: Süre bittiğinde emir iptal edilir; pozisyon açılmaz.\n\n• Keep Until Validity Ends: Belirlenen süre bitene kadar beklenir; süreç içinde fiyat limite dokunursa işlem açılır.\n\n• Re-price Next Candle: Sonraki mumda yeni piyasa bilgisine göre limit fiyatı yeniden hesaplanır.\n\n• Convert to Market Order: Limit dolmazsa emir o andaki piyasa fiyatından açılır. İşlem kaçmaz, fakat giriş fiyatı kötüleşebilir.\n\nÖrnek: Limit alış 99.50, fiyat 100'den 103'e gitti ve limite dönmedi. Convert to Market Order daha yüksek fiyattan pozisyona sokar; Cancel Order işlem açmaz.",
  },
  partialFill: {
    title: "Partial Fill",
    body: "Gerçek piyasada verilen emrin tamamı aynı anda karşılanmayabilir. Bu alan, emrin yalnızca bir kısmı dolduğunda backtestin ne kabul edeceğini söyler.\n\n• Not Allowed: Emir tam miktarda dolmadıkça pozisyon açılmış sayılmaz.\n\n• Allowed: Dolan miktar kadar pozisyon açılır; sonuçlar daha küçük açık pozisyon üzerinden hesaplanır.\n\n• Minimum 50% Fill: Emrin en az yarısı dolmuşsa işlem geçerli kabul edilir.\n\n• Fill Remaining as Market: Dolmayan bölüm, piyasa fiyatından tamamlanır; slippage doğabilir.\n\n• Cancel Remaining: Dolan bölüm korunur; geri kalan emir iptal edilir.\n\nÖrnek: 10 birimlik emirden yalnızca 6 birim dolduysa, Minimum 50% Fill işlemi kabul eder; Not Allowed kabul etmez.",
  },
  intrabarFunding: {
    title: "Intrabar / Funding",
    body: "Bu alan iki ayrı gerçekçilik katmanını yönetir: mumun içindeki fiyat sırasını görmek için daha detaylı veri kullanımı ve kaldıraçlı perpetual işlemlerde periyodik fonlama maliyetinin sonuca eklenmesi.\n\nÖrnek: Aynı 15 dakikalık mum içinde hem stop hem kâr hedefi görünüyorsa, tick verisi hangi seviyenin önce çalıştığını gösterebilir.",
  },
  useTickData: {
    title: "Use Tick Data",
    body: "Tick data, mumun içindeki fiyat hareketini daha ayrıntılı görmek için kullanılır. Bu alan artık sade bir aç/kapat tercihi olarak düşünülmeli.\n\n• None: Bu strateji için tick data tercihi belirtilmez; sistem genel varsayıma dönebilir.\n\n• Yes: Tick data mevcutsa giriş, çıkış, stop ve intrabar kontrolünde daha ayrıntılı fiyat akışı kullanılabilir.\n\n• No: Tick data kullanılmaz; hesaplama OHLCV mum verisi üzerinden yapılır.\n\nÖrnek: Aynı mum içinde hem stop hem take profit görünüyorsa tick data varsa önce hangisinin çalıştığı daha doğru anlaşılır. Tick data yoksa motor seçilen muhafazakâr varsayıma göre karar verir.",
  },
  fundingFee: {
    title: "Funding Fee",
    body: "Perpetual vadeli işlemlerde açık pozisyon belirli saatlerde fonlama ödemesi yapabilir veya alabilir. Bu seçenek, funding etkisinin tarihsel veriyle uygulanıp uygulanmayacağını belirler.\n\n• Use Historical Funding Data: Test tarihindeki gerçek funding oranları uygulanır. Veri mevcutsa en gerçekçi seçenektir.\n\n• Disabled: Funding etkisi sonuçlara eklenmez.\n\nÖrnek: Long pozisyon üç funding döneminden geçtiyse, her dönemdeki maliyet işlem kârından düşülür veya pozisyona göre eklenir.",
  },
  fundingSource: {
    title: "Funding Source",
    body: "Funding Fee aktif olduğunda hesaplamada kullanılacak oranların hangi veri kaynağından geleceğini belirler. Test edilen piyasa ile veri kaynağının eşleşmesi önemlidir.\n\n• Binance Historical Funding: Binance perpetual sözleşmesine ait geçmiş funding oranları kullanılır.\n\n• Bybit Historical Funding: Bybit perpetual piyasasının geçmiş oranları kullanılır.\n\n• Manual Funding Source: Kullanıcı kendi girdiği oran veya tabloyu kullanır.\n\nÖrnek: Binance BTCUSDT perpetual üzerinde test yapıyorsan, Binance tarihsel funding verisini kullanmak sonuçla işlem ortamını uyumlu tutar.",
  },
  protectionStopLogic: {
    title: "5. Protection / Stop Logic",
    body: "Bu bölüm, açık pozisyonun risk nedeniyle hangi koşullarda kapatılacağını belirler. Entry veya normal Exit mantığından bağımsız koruma katmanıdır. Birden fazla stop kuralı aynı anda aktif olabilir.\n\nÖrnek: Pozisyon %1 zarar görürse Percentage Stop kapanış üretir. Ancak fiyat zarara ulaşmadan indikatör ters sinyal verirse Logic-Based Stop Block daha önce çalışabilir.",
  },
  stopRules: {
    title: "Stop Rules",
    body: "Bu alandaki her stop türü eşit seviyede bir koruma kuralıdır ve solundaki checkbox ile aktif edilir. Logic-Based Stop Block indikatör/condition ile; Percentage Stop sabit zarar mesafesiyle; Trailing Stop kârı takip ederek; Absolute Price Stop belirli fiyat seviyesinde çalışır.\n\nAktif kuralların birbirleriyle nasıl karar vereceğini Stop Mode belirler.",
  },
  percentageStop: {
    title: "Percentage Stop",
    body: "Giriş fiyatından itibaren pozisyonun aleyhine belirlenen yüzde kadar hareket olduğunda stop üretir. İndikatör beklemez; fiyat mesafesine dayanır.\n\nÖrnek: Long işlem 100 fiyattan açıldı ve Stop Distance %1.00 seçildi. Fiyat 99'a düşerse Percentage Stop tetiklenir.",
  },
  trailingStop: {
    title: "Trailing Stop",
    body: "Fiyat belirli miktarda kâra ulaştıktan sonra aktifleşen ve fiyat lehine ilerledikçe stop seviyesini taşıyan korumadır. Amaç, kazanan pozisyonun bir kısmını geri vermeden trendin devamına alan bırakmaktır.\n\nÖrnek: Long işlem 100'den açıldı. Activate After Profit %2 ise trailing 102'de devreye girer. Trailing Distance %0.8 ise fiyat 105'e ulaştığında stop yaklaşık 104.16 seviyesine kadar yükselmiş olur.",
  },
  basePositionSize: {
    title: "Base Position Size",
    body: "İşleme doğrudan sermayenin belirli bir yüzdesiyle girmek için kullanılan pozisyon boyutu yöntemidir. Seçildiğinde Risk Per Trade ve Custom Formula pasif hale gelir; çünkü tek işlem için iki farklı boyutlandırma yöntemi aynı anda kullanılamaz.\n\nÖrnek: Equity 10.000 USD ve Position Size %10 ise ilk pozisyon nominal olarak 1.000 USD üzerinden oluşturulur; kaldıraç etkisi ayrıca uygulanır.",
  },
  riskPerTrade: {
    title: "Risk Per Trade",
    body: "Pozisyon büyüklüğünü, stop gerçekleşirse kaybedilecek toplam sermaye oranına göre hesaplatır. Bu yöntemin çalışabilmesi için kullanılacak stop mesafesi motor tarafından bilinmelidir.\n\nÖrnek: Equity 10.000 USD, risk %1 ise maksimum zarar 100 USD'dir. Stop mesafesi %2 ise sistem, stopta yaklaşık 100 USD kaybettirecek pozisyon miktarını hesaplar.",
  },
  customFormula: {
    title: "Custom Formula",
    body: "Pozisyon büyüklüğünün kullanıcının tanımladığı formülle hesaplanmasını sağlar. Formül; equity, volatilite, sinyal gücü veya başka değişkenleri kullanabilir. Seçildiğinde diğer iki boyutlandırma yöntemi pasif kalır.\n\nÖrnek: positionSize = equity * 0.05 * volatilityAdjustment düşük volatilitede daha büyük, yüksek volatilitede daha küçük pozisyon üretebilir.",
  },
  maxSinglePosition: {
    title: "Max Single Position",
    body: "Tek bir pozisyonun ulaşabileceği maksimum büyüklüğü sınırlar. Base Position Size, Risk Per Trade veya Custom Formula daha büyük bir miktar hesaplamış olsa bile bu sınır aşılmaz.\n\nÖrnek: Max Single Position %25 ise bir sinyal çok güçlü görünse bile tek pozisyon equity'nin %25'inden büyük açılamaz.",
  },
  maxTotalExposure: {
    title: "Max Total Exposure",
    body: "Aynı stratejiye ait açık pozisyonların ve scaling ile eklenen layer'ların toplam büyüklük sınırıdır. Scaling Logic bu değeri aşacak yeni kademe oluşturamaz.\n\nÖrnek: Açık ana pozisyon %10 ve ek layer'lar toplam %35'e ulaştıysa, Max Total Exposure %40 iken yeni %10 layer açılamaz.",
  },
  leverageMode: {
    title: "Leverage Mode",
    body: "Kaldıraçlı pozisyonun teminat yapısını belirler.\n\n• No Leverage: Pozisyon kaldıraç kullanılmadan hesaplanır.\n\n• Isolated: Pozisyona ayrılan teminat o pozisyonla sınırlıdır; zarar doğrudan tüm hesabın marjinini kullanmaz.\n\n• Cross: Uygun hesap bakiyesi açık pozisyonun marjinini destekleyebilir; risk hesabı tüm açık marjin ilişkisini dikkate almalıdır.\n\nÖrnek: Isolated 5x seçilmiş pozisyonda, o işlem için ayrılan teminat ve likidasyon davranışı ayrı hesaplanır.",
  },
  signalStrengthSizing: {
    title: "Signal Strength Sizing",
    body: "Bu bölüm, sinyal gücünün pozisyon büyüklüğünü ancak seçilen Condition Package sağlandığında etkilemesini sağlar.",
  },
  stopExitConflict: {
    title: "Stop + Exit",
    body: "Aynı mumda hem risk kaynaklı Stop sinyali hem de normal Exit sinyali oluşursa pozisyon kapatılır; ancak kapanışın hangi nedenle kaydedileceği ve yürütme önceliği bu menüyle belirlenir.\n\n• Stop Has Priority: Kapanış risk koruması olarak kaydedilir; özellikle stop performans analizinde tutarlılık sağlar.\n\n• Exit Has Priority: Normal çıkış sinyali esas alınır.\n\n• Record Both Reasons: Tek kapanış uygulanır fakat raporda iki neden de saklanır.\n\n• First Trigger Wins: İntrabar veri mevcutsa önce gerçekleşen tetikleyici kapanış nedeni olur.\n\nÖrnek: Long pozisyonda fiyat hem yüzde stop seviyesine dokunuyor hem de exit indikatörü ters sinyal üretiyorsa, Stop Has Priority seçimi kapanışı stop olarak raporlar.",
  },
  multipleStopsConflict: {
    title: "Multiple Stops",
    body: "Aynı pozisyon için birden fazla aktif stop kuralı aynı anda veya aynı mum içinde tetiklenebilir. Bu menü hangi stop seviyesinin uygulanacağını ve sonuçlarda hangi nedenin raporlanacağını belirler.\n\n• First Trigger Wins: Fiyat akışında ilk tetiklenen stop uygulanır; ayrıntılı veri mevcutsa doğrudan okunabilir.\n\n• Most Conservative Stop Wins: Pozisyonu daha erken kapatan ve daha az risk bırakan stop seçilir.\n\n• Priority Order: Önceden tanımlanan stop sıralaması esas alınır.\n\n• Record All / Execute Highest Priority: Bir stop uygulanır, fakat aynı anda çalışan diğer stoplar rapora eklenir.\n\nÖrnek: Aynı mumda Percentage Stop ve Logic-Based Stop Block tetiklenirse, Record All seçimi kapanışı tek kez uygular fakat analizde iki tetikleyiciyi de gösterir.",
  },
};

// ---------------------------------------------------------------------------
// Enum option lists — VALUE mirrors domain/strategy/config.py Literal members;
// LABEL is the V18 spec surface (doc 02 §5). Selects with a required-no-default
// field carry a leading "Choose…" empty option (see the form component).
// ---------------------------------------------------------------------------

export interface SelectOption {
  value: string;
  label: string;
}

export const ENTRY_TIMING_OPTIONS: SelectOption[] = [
  { value: "next_candle_open", label: "Next Candle Open" },
  { value: "current_candle_close", label: "Current Candle Close" },
  { value: "next_candle_close", label: "Next Candle Close" },
  { value: "intrabar_touch", label: "Intrabar Touch" },
  { value: "limit_fill_simulation", label: "Limit Fill Simulation" },
  { value: "market_fill_simulation", label: "Market Fill Simulation" },
];

export const EXIT_TIMING_OPTIONS: SelectOption[] = [
  { value: "next_candle_open", label: "Next Candle Open" },
  { value: "current_candle_close", label: "Current Candle Close" },
  { value: "next_candle_close", label: "Next Candle Close" },
  { value: "intrabar_touch", label: "Intrabar Touch" },
  { value: "stop_limit_priority_simulation", label: "Stop / Limit Priority Simulation" },
  { value: "market_fill_simulation", label: "Market Fill Simulation" },
];

export const ORDER_TYPE_OPTIONS: SelectOption[] = [
  { value: "market_order", label: "Market Order" },
  { value: "limit_order", label: "Limit Order" },
  { value: "stop_order", label: "Stop Order" },
  { value: "stop_limit_order", label: "Stop-Limit Order" },
  { value: "simulation_only", label: "Simulation Only" },
];

// Order types that reveal the conditional Limit Order Details subtree (§5.2.1).
export const LIMIT_ORDER_TYPES = new Set(["limit_order", "stop_limit_order"]);

export const LIMIT_PRICE_RULE_OPTIONS: SelectOption[] = [
  { value: "entry_signal_price", label: "Entry signal price" },
  { value: "best_bid_ask", label: "Best bid / ask" },
  { value: "signal_price_minus_offset", label: "Signal price minus offset" },
  { value: "signal_price_plus_offset", label: "Signal price plus offset" },
];

export const LIMIT_VALIDITY_OPTIONS: SelectOption[] = [
  { value: "current_candle_only", label: "Current candle only" },
  { value: "1_candle", label: "1 candle" },
  { value: "2_candles", label: "2 candles" },
  { value: "3_candles", label: "3 candles" },
  { value: "4_candles", label: "4 candles" },
  { value: "until_cancelled", label: "Until cancelled" },
];

export const UNFILLED_POLICY_OPTIONS: SelectOption[] = [
  { value: "cancel_order", label: "Cancel Order" },
  { value: "keep_until_validity_ends", label: "Keep Until Validity Ends" },
  { value: "re_price_next_candle", label: "Re-price Next Candle" },
  { value: "convert_to_market_order", label: "Convert to Market Order" },
];

export const PARTIAL_FILL_OPTIONS: SelectOption[] = [
  { value: "not_allowed", label: "Not Allowed" },
  { value: "allowed", label: "Allowed" },
  { value: "minimum_50_percent", label: "Minimum 50% Fill" },
  { value: "fill_remaining_as_market", label: "Fill Remaining as Market" },
  { value: "cancel_remaining", label: "Cancel Remaining" },
];

export const SLIPPAGE_MODE_OPTIONS: SelectOption[] = [
  { value: "percentage_slippage", label: "Percentage Slippage" },
  { value: "historical_slippage_if_available", label: "Historical Slippage If Available" },
];

export const TICK_POLICY_OPTIONS: SelectOption[] = [
  { value: "inherit", label: "None (inherit)" },
  { value: "require", label: "Yes (require)" },
  { value: "disable", label: "No (disable)" },
];

export const SIZING_METHOD_OPTIONS: SelectOption[] = [
  { value: "base_position_size", label: "Base Position Size" },
  { value: "risk_based_sizing", label: "Risk Per Trade" },
  { value: "formula_based_sizing", label: "Custom Formula" },
];

export const FORMULA_TYPE_OPTIONS: SelectOption[] = [
  { value: "kelly_criterion", label: "Kelly Criterion" },
  { value: "custom_formula", label: "Custom Formula" },
];

export const SIGNAL_STRENGTH_OPTIONS: SelectOption[] = [
  { value: "no_adjustment", label: "No Signal Strength Adjustment" },
  { value: "volatility_adjusted", label: "Volatility Adjusted" },
  { value: "trend_adjusted", label: "Trend Adjusted" },
  { value: "divergence_adjusted", label: "Divergence Adjusted" },
];

export const LEVERAGE_MODE_OPTIONS: SelectOption[] = [
  { value: "isolated", label: "Isolated" },
  { value: "cross", label: "Cross" },
];

export const OVERLAPPING_SIGNAL_OPTIONS: SelectOption[] = [
  { value: "queue_sequential", label: "Queue Sequential" },
  { value: "cancel_pending", label: "Cancel Pending" },
  { value: "merge_signals", label: "Merge Signals" },
  { value: "ignore_if_active", label: "Ignore If Active" },
];

export const SAME_DIRECTION_OPTIONS: SelectOption[] = [
  { value: "allow_stacking", label: "Allow Stacking" },
  { value: "replace_existing", label: "Replace Existing" },
  { value: "scale_existing", label: "Scale Existing" },
  { value: "ignore", label: "Ignore" },
];

export const OPPOSITE_HEDGE_OPTIONS: SelectOption[] = [
  { value: "allow_hedge", label: "Allow Hedge" },
  { value: "close_existing", label: "Close Existing" },
  { value: "ignore", label: "Ignore" },
];

// ---------------------------------------------------------------------------
// Form state — a flat, string-backed mirror of the covered payload sections.
// Numeric fields stay strings so a blank field is representable ("" → omit on
// merge) and no binary-float artifact ever reaches the Decimal-typed backend
// (decimals travel as strings, which Pydantic parses exactly).
// ---------------------------------------------------------------------------

export interface StrategyFlatForm {
  data: {
    instrument_id: string;
    market_dataset_root_id: string;
    market_dataset_revision_id: string;
    market_dataset_content_hash: string;
    backtest_start: string;
    backtest_end: string;
    initial_capital: string;
    entry_timing: string;
    exit_timing: string;
    order_type: string;
    limit_price_rule: string;
    limit_price_offset: string;
    limit_validity: string;
    limit_unfilled_policy: string;
    limit_partial_fill_policy: string;
    commission: string;
    spread: string;
    slippage_mode: string;
    slippage_value: string;
    tick_policy: string;
    funding_enabled: boolean;
    funding_source_root_id: string;
    funding_source_revision_id: string;
    funding_source_content_hash: string;
  };
  protection: {
    percentage_enabled: boolean;
    percentage_loss: string;
    trailing_enabled: boolean;
    trailing_trail: string;
    trailing_lock_in: string;
    absolute_enabled: boolean;
    absolute_price: string;
  };
  sizing: {
    method: string;
    base_position_size: string;
    risk_percentage_per_trade: string;
    risk_stop_loss_point: string;
    formula_type: string;
    signal_strength_adjustment: string;
    leverage_mode: string;
    min_position_size: string;
    max_position_size: string;
  };
  conflict: {
    overlapping_signal_policy: string;
    same_direction_stacking: string;
    opposite_direction_hedge: string;
    exit_on_opposite_signal: boolean;
  };
}

// config.py defaults (only for enum fields that carry a Field default — the
// required-no-default enums start blank so the server, not the form, decides).
const DEFAULTS = {
  order_type: "market_order",
  limit_validity: "3_candles",
  limit_partial_fill_policy: "not_allowed",
  slippage_mode: "percentage_slippage",
  tick_policy: "inherit",
  method: "base_position_size",
  signal_strength_adjustment: "no_adjustment",
  leverage_mode: "isolated",
  overlapping_signal_policy: "queue_sequential",
  same_direction_stacking: "allow_stacking",
  opposite_direction_hedge: "allow_hedge",
  percentage_loss: "1.0",
  trailing_trail: "2.0",
  trailing_lock_in: "0.8",
} as const;

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

// Render a scalar payload value as an input string ("" for null/undefined).
function str(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

function bool(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function enumStr(value: unknown, fallback: string): string {
  return typeof value === "string" && value !== "" ? value : fallback;
}

export function extractFlatSections(payload: Record<string, unknown>): StrategyFlatForm {
  const data = asRecord(payload.data);
  const range = asRecord(data.backtest_range);
  const execution = asRecord(data.execution);
  const order = asRecord(data.order_config);
  const limit = asRecord(order.limit);
  const costs = asRecord(data.costs);
  const intrabar = asRecord(data.intrabar_policy);
  const funding = asRecord(data.funding);

  const stops = asRecord(payload.protection_stop_logic);
  const pct = asRecord(stops.percentage_stop);
  const trail = asRecord(stops.trailing_stop);
  const abs = asRecord(stops.absolute_stop);

  const sizing = asRecord(payload.position_sizing);
  const risk = asRecord(sizing.risk_based);
  const formula = asRecord(sizing.formula_based);
  const limits = asRecord(sizing.position_size_limits);

  const conflict = asRecord(payload.conflict_position_handling);

  return {
    data: {
      instrument_id: str(data.instrument_id),
      market_dataset_root_id: str(data.market_dataset_root_id),
      market_dataset_revision_id: str(data.market_dataset_revision_id),
      market_dataset_content_hash: str(data.market_dataset_content_hash),
      backtest_start: str(range.start),
      backtest_end: str(range.end),
      initial_capital: str(data.initial_capital),
      entry_timing: str(execution.entry_timing),
      exit_timing: str(execution.exit_timing),
      order_type: enumStr(order.type, DEFAULTS.order_type),
      limit_price_rule: str(limit.price_rule),
      limit_price_offset: str(limit.price_offset),
      limit_validity: enumStr(limit.validity, DEFAULTS.limit_validity),
      limit_unfilled_policy: str(limit.unfilled_policy),
      limit_partial_fill_policy: enumStr(
        limit.partial_fill_policy,
        DEFAULTS.limit_partial_fill_policy,
      ),
      commission: str(costs.commission),
      spread: str(costs.spread),
      slippage_mode: enumStr(costs.slippage_mode, DEFAULTS.slippage_mode),
      slippage_value: str(costs.slippage_value),
      tick_policy: enumStr(intrabar.tick_policy, DEFAULTS.tick_policy),
      funding_enabled: bool(funding.enabled, false),
      funding_source_root_id: str(funding.source_root_id),
      funding_source_revision_id: str(funding.source_revision_id),
      funding_source_content_hash: str(funding.source_content_hash),
    },
    protection: {
      percentage_enabled: bool(pct.enabled, false),
      percentage_loss: str(pct.loss_percentage) || DEFAULTS.percentage_loss,
      trailing_enabled: bool(trail.enabled, false),
      trailing_trail: str(trail.trail_percentage) || DEFAULTS.trailing_trail,
      trailing_lock_in: str(trail.lock_in_percentage) || DEFAULTS.trailing_lock_in,
      absolute_enabled: bool(abs.enabled, false),
      absolute_price: str(abs.absolute_price),
    },
    sizing: {
      method: enumStr(sizing.method, DEFAULTS.method),
      base_position_size: str(sizing.base_position_size),
      risk_percentage_per_trade: str(risk.risk_percentage_per_trade),
      risk_stop_loss_point: str(risk.stop_loss_point),
      formula_type: enumStr(formula.formula_type, "kelly_criterion"),
      signal_strength_adjustment: enumStr(
        sizing.signal_strength_adjustment,
        DEFAULTS.signal_strength_adjustment,
      ),
      leverage_mode: enumStr(sizing.leverage_mode, DEFAULTS.leverage_mode),
      min_position_size: str(limits.min_position_size),
      max_position_size: str(limits.max_position_size),
    },
    conflict: {
      overlapping_signal_policy: enumStr(
        conflict.overlapping_signal_policy,
        DEFAULTS.overlapping_signal_policy,
      ),
      same_direction_stacking: enumStr(
        conflict.same_direction_stacking,
        DEFAULTS.same_direction_stacking,
      ),
      opposite_direction_hedge: enumStr(
        conflict.opposite_direction_hedge,
        DEFAULTS.opposite_direction_hedge,
      ),
      exit_on_opposite_signal: bool(conflict.exit_on_opposite_signal, true),
    },
  };
}

// A trimmed non-empty decimal string, else undefined (→ key omitted). Decimals
// travel as strings so Pydantic parses them exactly (no float artifact).
function decOrOmit(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

// A non-empty enum string, else undefined (→ key omitted so a required-no-
// default field reports "field required" and a defaulted field takes its
// default — the server decides, never the form).
function enumOrOmit(value: string): string | undefined {
  return value === "" ? undefined : value;
}

function pruneUndefined(obj: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (value !== undefined) out[key] = value;
  }
  return out;
}

// Overlay the four covered sections onto the FULL payload, preserving every
// uncovered key (identity, position_entry_logic, position_exit_logic,
// scaling_logic, restrictions_filters, …). This is the merge behind "Apply
// structured changes" → PATCH full payload.
export function mergeFlatSections(
  payload: Record<string, unknown>,
  form: StrategyFlatForm,
): Record<string, unknown> {
  const d = form.data;
  const isLimit = LIMIT_ORDER_TYPES.has(d.order_type);

  const order: Record<string, unknown> = { type: d.order_type };
  if (isLimit) {
    order.limit = pruneUndefined({
      price_rule: enumOrOmit(d.limit_price_rule),
      price_offset: decOrOmit(d.limit_price_offset),
      validity: enumOrOmit(d.limit_validity),
      unfilled_policy: enumOrOmit(d.limit_unfilled_policy),
      partial_fill_policy: enumOrOmit(d.limit_partial_fill_policy),
    });
  }

  const funding: Record<string, unknown> = { enabled: d.funding_enabled };
  if (d.funding_enabled) {
    Object.assign(
      funding,
      pruneUndefined({
        source_root_id: decOrOmit(d.funding_source_root_id),
        source_revision_id: decOrOmit(d.funding_source_revision_id),
        source_content_hash: decOrOmit(d.funding_source_content_hash),
      }),
    );
  }

  const data: Record<string, unknown> = pruneUndefined({
    instrument_id: decOrOmit(d.instrument_id),
    market_dataset_root_id: decOrOmit(d.market_dataset_root_id),
    market_dataset_revision_id: decOrOmit(d.market_dataset_revision_id),
    market_dataset_content_hash: decOrOmit(d.market_dataset_content_hash),
    backtest_range:
      d.backtest_start.trim() === "" && d.backtest_end.trim() === ""
        ? undefined
        : pruneUndefined({ start: decOrOmit(d.backtest_start), end: decOrOmit(d.backtest_end) }),
    initial_capital: decOrOmit(d.initial_capital),
    execution: pruneUndefined({
      entry_timing: enumOrOmit(d.entry_timing),
      exit_timing: enumOrOmit(d.exit_timing),
    }),
    order_config: order,
    costs: pruneUndefined({
      commission: decOrOmit(d.commission),
      spread: decOrOmit(d.spread),
      slippage_mode: d.slippage_mode,
      slippage_value: decOrOmit(d.slippage_value),
    }),
    intrabar_policy: { tick_policy: d.tick_policy },
    funding,
  });

  const p = form.protection;
  const protection: Record<string, unknown> = {
    percentage_stop: pruneUndefined({
      enabled: p.percentage_enabled,
      loss_percentage: decOrOmit(p.percentage_loss),
    }),
    trailing_stop: pruneUndefined({
      enabled: p.trailing_enabled,
      trail_percentage: decOrOmit(p.trailing_trail),
      lock_in_percentage: decOrOmit(p.trailing_lock_in),
    }),
    absolute_stop: pruneUndefined({
      enabled: p.absolute_enabled,
      absolute_price: decOrOmit(p.absolute_price),
    }),
  };

  const s = form.sizing;
  const sizing: Record<string, unknown> = pruneUndefined({
    method: s.method,
    base_position_size:
      s.method === "base_position_size" ? decOrOmit(s.base_position_size) : undefined,
    risk_based:
      s.method === "risk_based_sizing"
        ? pruneUndefined({
            risk_percentage_per_trade: decOrOmit(s.risk_percentage_per_trade),
            stop_loss_point: decOrOmit(s.risk_stop_loss_point),
          })
        : undefined,
    formula_based:
      s.method === "formula_based_sizing"
        ? {
            formula_type: s.formula_type,
            // Preserve any Kelly / custom params set via the Advanced editor.
            formula_params: asRecord(
              asRecord(asRecord(payload.position_sizing).formula_based).formula_params,
            ),
          }
        : undefined,
    signal_strength_adjustment: s.signal_strength_adjustment,
    leverage_mode: s.leverage_mode,
    position_size_limits:
      s.min_position_size.trim() === "" && s.max_position_size.trim() === ""
        ? undefined
        : pruneUndefined({
            min_position_size: decOrOmit(s.min_position_size),
            max_position_size: decOrOmit(s.max_position_size),
          }),
  });

  const c = form.conflict;
  const conflict: Record<string, unknown> = {
    overlapping_signal_policy: c.overlapping_signal_policy,
    same_direction_stacking: c.same_direction_stacking,
    opposite_direction_hedge: c.opposite_direction_hedge,
    exit_on_opposite_signal: c.exit_on_opposite_signal,
  };

  return {
    ...payload,
    data,
    protection_stop_logic: protection,
    position_sizing: sizing,
    conflict_position_handling: conflict,
  };
}
