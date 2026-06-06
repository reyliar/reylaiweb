const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store"
};

const TEXT_HEADERS = {
  "content-type": "text/plain; charset=utf-8",
  "cache-control": "no-store"
};

const VALID_ID = /^[A-Za-z0-9_-]{6,200}$/;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_CONTEXT_PAGES = 8;
const CONTEXT_CHAR_LIMIT = 24000;
const FALLBACK_CHAR_LIMIT = 9000;

type Book = {
  book_id?: string;
  drive_id?: string;
  name?: string;
  title?: string;
  grade?: string;
  local_path?: string;
  pdf_url?: string;
  source_url?: string;
  remote_url?: string;
  pdf_source?: string;
  cover_url?: string;
  cover_data_url?: string;
  scan_status?: string;
  scan_pages?: number;
  scan_extractor?: string;
  added_at?: string;
  updated_at?: string;
  cover_updated_at?: string;
};

type ScanPage = {
  page?: number;
  text?: string;
};

type ScanData = {
  total_pages?: number;
  pages?: ScanPage[];
  extractor?: string;
};

type AnalyzePayload = {
  book_id?: string;
  drive_id?: string;
  book_name?: string;
  prompt?: string;
  title_requested?: boolean;
  chat_history?: Array<{ role?: string; text?: string }>;
};

type MistralMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export default {
  async fetch(request, env): Promise<Response> {
    try {
      return await handleRequest(request, env);
    } catch (error) {
      console.error(JSON.stringify({
        level: "error",
        message: error instanceof Error ? error.message : String(error)
      }));
      return json({ error: "Sunucu hatası." }, 500);
    }
  }
} satisfies ExportedHandler<Env>;

async function handleRequest(request: Request, env: Env): Promise<Response> {
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(request) });
  }

  const url = new URL(request.url);
  const path = url.pathname;

  if (!path.startsWith("/api/")) {
    return text("Not found", 404);
  }

  if (request.method === "GET" && path === "/api/health") {
    return json({ ok: true, service: "reylai-api" });
  }

  if (request.method === "GET" && path === "/api/library") {
    return handleLibrary(url, env);
  }

  if (path === "/api/chat_history") {
    if (request.method === "GET") return json({ chats: [] });
    if (request.method === "POST" || request.method === "PUT") {
      return json({ success: true, store: { chats: [] }, remote_disabled: true });
    }
  }

  if (request.method === "DELETE" && path.startsWith("/api/chat_history/")) {
    return json({ success: true, store: { chats: [] }, remote_disabled: true });
  }

  if (path === "/api/config") {
    if (request.method === "GET") return handleConfig(env);
    if (request.method === "POST") return json({ success: false, error: "Statik yayında ayar kaydetme kapalı." }, 405);
  }

  if (request.method === "GET" && path === "/api/debug_gas") {
    return handleDebugGas(env);
  }

  if (request.method === "POST" && path === "/api/sync_cloud") {
    return json({ success: true, uploaded: 0, skipped: 0, errors: [], static_hosted: true });
  }

  if (request.method === "POST" && path === "/api/analyze") {
    return handleAnalyze(request, env);
  }

  if (request.method === "POST" && path === "/api/analyze_start") {
    const data = await readJson<AnalyzePayload>(request);
    const response = await analyzePayload(data, env);
    return json({ success: !response.error, analysis_id: crypto.randomUUID(), ...response });
  }

  if (request.method === "GET" && path.startsWith("/api/analyze_status/")) {
    return json({ done: true, message: "Hazır" });
  }

  if (request.method === "GET" && path.startsWith("/api/scan_status/")) {
    const id = safeId(path.split("/").pop() || "");
    if (!id) return json({ scan_status: "failed", scan_pages: 0 }, 400);
    const scan = await fetchScanData(env, [id]);
    if (!scan) return json({ scan_status: "failed", scan_pages: 0 });
    return json({
      scan_status: "done",
      scan_pages: scan.total_pages || scan.pages?.length || 0,
      scan_extractor: publicScanExtractor(scan.extractor || "")
    });
  }

  if (request.method === "GET" && path.startsWith("/api/cover/")) {
    const id = safeId(path.split("/").pop() || "");
    if (!id) return text("", 404);
    return redirectIfExists(env, `/reylai_assets/covers/${encodeURIComponent(id)}.jpg`);
  }

  if (request.method === "GET" && path.startsWith("/api/serve_pdf/")) {
    const id = safeId(path.split("/").pop() || "");
    if (!id) return text("PDF bulunamadı", 404);
    return handleServePdf(id, env);
  }

  if (request.method === "GET" && path.startsWith("/api/page_image/")) {
    return text("Statik yayında sayfa görseli üretimi desteklenmiyor.", 404);
  }

  if (
    ["POST", "PUT", "DELETE"].includes(request.method) &&
    ["/api/upload", "/api/add_book", "/api/delete", "/api/rename_book", "/api/update_cover", "/api/scan_missing_books", "/api/scan_missing_books_cancel"].some((prefix) => path.startsWith(prefix))
  ) {
    return json({ success: false, error: "Bu işlem statik Cloudflare yayında desteklenmiyor." }, 405);
  }

  if (request.method === "GET" && path === "/api/scan_missing_books_status") {
    return json({
      running: false,
      completed: true,
      total: 0,
      processed: 0,
      success: 0,
      failed: 0,
      already_ready: 0,
      current_message: "Statik yayında tarama işi yok.",
      logs: []
    });
  }

  if (request.method === "POST" && path === "/api/verify_password") {
    return json({ success: false, error: "Statik yayında yönetim işlemleri kapalı." }, 403);
  }

  return json({ error: "API endpoint bulunamadı." }, 404);
}

async function handleLibrary(url: URL, env: Env): Promise<Response> {
  const grade = url.searchParams.get("grade") || "";
  const books = await fetchLibrary(env);
  const filtered = books.filter((book) => !grade || (book.grade || "9") === grade);
  const enriched = await Promise.all(filtered.map((book) => enrichBook(book, env)));
  return json(enriched);
}

async function handleConfig(env: Env): Promise<Response> {
  const config = await fetchStaticJson<Record<string, unknown>>(env, "/reylai_config.json");
  return json(config || { folder_ids: {} });
}

async function handleDebugGas(env: Env): Promise<Response> {
  if (!env.GAS_WEB_APP_URL) {
    return json({ error: "GAS_WEB_APP_URL ayarlanmamış" }, 500);
  }
  const results: Record<string, unknown> = {};
  for (const grade of ["9", "10"]) {
    const target = new URL(env.GAS_WEB_APP_URL);
    target.searchParams.set("action", "list");
    target.searchParams.set("grade", grade);
    try {
      const response = await fetch(target.toString(), { redirect: "follow" });
      results[grade] = {
        status: response.status,
        raw: await readTextSnippet(response, 2000)
      };
    } catch (error) {
      results[grade] = { error: error instanceof Error ? error.message : String(error) };
    }
  }
  return json(results);
}

async function handleAnalyze(request: Request, env: Env): Promise<Response> {
  const payload = await readJson<AnalyzePayload>(request);
  const response = await analyzePayload(payload, env);
  return json(response, response.error ? 400 : 200);
}

async function analyzePayload(payload: AnalyzePayload, env: Env): Promise<Record<string, unknown>> {
  const prompt = String(payload.prompt || "").trim();
  const selectedId = safeId(payload.book_id || payload.drive_id || "");
  const bookName = String(payload.book_name || "Kitap").trim() || "Kitap";

  if (!env.MISTRAL_API_KEY) return { error: "MISTRAL_API_KEY yapılandırılmamış." };
  if (!prompt) return { error: "Prompt eksik." };
  if (!selectedId) return { error: "book_id eksik." };

  const smallTalk = smallTalkResponse(prompt);
  if (smallTalk) {
    return {
      result: smallTalk,
      local: true,
      chat_title: payload.title_requested ? fallbackChatTitle(prompt) : ""
    };
  }

  const library = await fetchLibrary(env);
  const book = findBook(library, selectedId);
  const scanKeys = scanKeysForBook(book, selectedId);
  const scanData = await fetchScanData(env, scanKeys);
  if (!scanData?.pages?.length) {
    return {
      error: "Seçili kitap için hazır tarama metni bulunamadı.",
      missing_scan: true
    };
  }

  const contextText = buildContextExcerpt(scanData.pages, prompt);
  if (!contextText) {
    return {
      error: "Seçili kitap için kullanılabilir tarama metni bulunamadı.",
      missing_scan: true
    };
  }

  const requestedPages = extractPageNumbers(prompt);
  const historyContext = buildHistoryContext(payload.chat_history || []);
  let systemMessage = [
    "Sen ReylAI adlı bir yapay zeka asistanısın.",
    "MEB ders kitaplarını analiz eder, öğrencilere ve öğretmenlere yardımcı olursun.",
    "Yalnızca verilen hazır tarama metnine dayan; kitapta olmayan bilgiyi uydurma.",
    "Bağlam yeterli değilse bunu açıkça söyle ve kullanıcıdan sayfa, soru numarası veya konu adı iste.",
    "Yanıtı Türkçe, sade ve öğrenciye yardımcı olacak biçimde ver.",
    "Soru çözüyorsan önce yöntemi, sonra sonucu ver.",
    "Mümkünse kaynak sayfayı [Sayfa X] formatında belirt.",
    "Matematiksel ifadeleri gerekiyorsa LaTeX ile yaz."
  ].join("\n");

  if (requestedPages.length) {
    systemMessage += `\n\nKullanıcı özellikle şu sayfa(lar)a odaklanıyor: ${requestedPages.join(", ")}.`;
  }
  if (historyContext) {
    systemMessage += "\n\nÖnceki konuşma özeti:\n" + historyContext;
  }
  systemMessage += "\n\nKitabın ilgili bölümleri:\n\n" + contextText;

  const messages: MistralMessage[] = [
    { role: "system", content: systemMessage },
    {
      role: "user",
      content: `Kitap adı: ${book?.title || book?.name || bookName}\nİstenen sayfalar: ${requestedPages.join(", ") || "belirtilmedi"}\n\nKullanıcı sorusu: ${prompt}`
    }
  ];

  try {
    const mistralResponse = await mistralChat(env, messages, { temperature: 0.2 });
    const result = mistralResponseText(mistralResponse);
    if (!result) return { error: "Mistral boş yanıt döndürdü." };

    let chatTitle = "";
    if (payload.title_requested) {
      chatTitle = await generateChatTitle(env, book?.title || book?.name || bookName, prompt, result);
    }
    return { result, chat_title: chatTitle };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const lower = message.toLowerCase();
    return {
      error: message,
      rate_limit: lower.includes("429") || lower.includes("quota") || lower.includes("rate limit"),
      temporary_unavailable: lower.includes("503") || lower.includes("unavailable") || lower.includes("high demand")
    };
  }
}

async function handleServePdf(id: string, env: Env): Promise<Response> {
  const library = await fetchLibrary(env);
  const book = findBook(library, id);
  const explicitUrl = firstValidUrl(book?.pdf_url, book?.source_url, book?.remote_url);
  if (explicitUrl) return Response.redirect(explicitUrl, 302);

  if (UUID_RE.test(id) && env.BOOKS_REMOTE_BASE_URL) {
    return Response.redirect(new URL(`${encodeURIComponent(id)}.pdf`, ensureSlash(env.BOOKS_REMOTE_BASE_URL)).toString(), 302);
  }

  if (book?.drive_id) {
    const driveUrl = `https://drive.google.com/uc?export=download&id=${encodeURIComponent(book.drive_id)}`;
    return Response.redirect(driveUrl, 302);
  }

  return text("PDF bulunamadı", 404);
}

async function enrichBook(book: Book, env: Env): Promise<Book> {
  const publicBook: Book = { ...book };
  const key = publicBook.book_id || publicBook.drive_id || "";
  const remotePdf = firstValidUrl(publicBook.pdf_url, publicBook.source_url, publicBook.remote_url);
  if (!publicBook.pdf_url && remotePdf) publicBook.pdf_url = remotePdf;
  if (!publicBook.pdf_url && publicBook.book_id && UUID_RE.test(publicBook.book_id) && env.BOOKS_REMOTE_BASE_URL) {
    publicBook.pdf_url = new URL(`${encodeURIComponent(publicBook.book_id)}.pdf`, ensureSlash(env.BOOKS_REMOTE_BASE_URL)).toString();
    publicBook.pdf_source ||= "book_archive";
  }
  if (key && !publicBook.cover_url && await staticExists(env, `/reylai_assets/covers/${encodeURIComponent(key)}.jpg`)) {
    publicBook.cover_url = `/api/cover/${encodeURIComponent(key)}`;
  }
  if (key) {
    const scan = await fetchScanData(env, [key]);
    if (scan) {
      publicBook.scan_status = "done";
      publicBook.scan_pages = scan.total_pages || scan.pages?.length || 0;
      publicBook.scan_extractor = publicScanExtractor(scan.extractor || "");
    }
  }
  return publicBook;
}

async function fetchLibrary(env: Env): Promise<Book[]> {
  const data = await fetchStaticJson<unknown>(env, "/reylai_library.json");
  return Array.isArray(data) ? data.filter(isBook) : [];
}

async function fetchScanData(env: Env, keys: string[]): Promise<ScanData | null> {
  for (const rawKey of keys) {
    const key = safeId(rawKey);
    if (!key) continue;
    const data = await fetchStaticJson<ScanData>(env, `/reylai_assets/scans/${encodeURIComponent(key)}.json`);
    if (data?.pages?.length) return data;
  }
  return null;
}

async function fetchStaticJson<T>(env: Env, path: string): Promise<T | null> {
  const response = await fetch(staticUrl(env, path), {
    headers: { "accept": "application/json" },
    cf: { cacheTtl: 60, cacheEverything: true }
  });
  if (!response.ok) return null;
  return await response.json() as T;
}

async function redirectIfExists(env: Env, path: string): Promise<Response> {
  if (!await staticExists(env, path)) return text("", 404);
  return Response.redirect(staticUrl(env, path), 302);
}

async function staticExists(env: Env, path: string): Promise<boolean> {
  const response = await fetch(staticUrl(env, path), {
    method: "HEAD",
    cf: { cacheTtl: 300, cacheEverything: true }
  });
  return response.ok;
}

async function mistralChat(
  env: Env,
  messages: MistralMessage[],
  options: { temperature?: number; maxTokens?: number } = {}
): Promise<unknown> {
  const payload: Record<string, unknown> = {
    model: env.MISTRAL_MODEL || "mistral-small-latest",
    messages,
    stream: false,
    temperature: options.temperature ?? 0.2,
    top_p: 0.9
  };
  if (options.maxTokens) payload.max_tokens = options.maxTokens;

  const response = await fetch(env.MISTRAL_CHAT_URL || "https://api.mistral.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      "authorization": `Bearer ${env.MISTRAL_API_KEY}`,
      "content-type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const snippet = await readTextSnippet(response, 500);
    throw new Error(`Mistral API hatası (${response.status}): ${snippet || response.statusText}`);
  }

  return await response.json();
}

function mistralResponseText(payload: unknown): string {
  if (!isRecord(payload) || !Array.isArray(payload.choices) || !isRecord(payload.choices[0])) return "";
  const message = payload.choices[0].message;
  if (!isRecord(message)) return "";
  const content = message.content;
  if (typeof content === "string") return content.trim();
  if (Array.isArray(content)) {
    return content.map((part) => {
      if (typeof part === "string") return part;
      if (isRecord(part) && typeof part.text === "string") return part.text;
      return "";
    }).join("").trim();
  }
  return "";
}

async function generateChatTitle(env: Env, bookName: string, prompt: string, answer: string): Promise<string> {
  const fallback = fallbackChatTitle(prompt);
  try {
    const titlePrompt = [
      "Aşağıdaki ders kitabı sohbeti için Türkçe, kısa ve doğal bir başlık yaz.",
      "Sadece başlığı döndür; tırnak, açıklama veya madde işareti kullanma.",
      "En fazla 6 kelime olsun.",
      "",
      `Kitap: ${bookName}`,
      `Kullanıcı sorusu: ${prompt}`,
      `Cevap özeti: ${answer.slice(0, 700)}`
    ].join("\n");
    const response = await mistralChat(env, [{ role: "user", content: titlePrompt }], {
      maxTokens: 32,
      temperature: 0.1
    });
    return cleanChatTitle(mistralResponseText(response)) || fallback;
  } catch {
    return fallback;
  }
}

function buildContextExcerpt(pages: ScanPage[], prompt: string): string {
  const selectedPages = pickContextPages(pages, prompt);
  const sourcePages = selectedPages.length ? selectedPages : pages.filter((page) => cleanPageText(page).length).slice(0, 3);
  const charLimit = selectedPages.length ? CONTEXT_CHAR_LIMIT : FALLBACK_CHAR_LIMIT;
  const parts: string[] = [];
  let total = 0;

  for (const page of sourcePages) {
    const pageNo = Number(page.page || 0);
    const text = cleanPageText(page);
    if (!pageNo || !text) continue;
    const part = `[Sayfa ${pageNo}]\n${text}`;
    if (total + part.length > charLimit) {
      const remaining = charLimit - total;
      if (remaining > 200) parts.push(part.slice(0, remaining));
      break;
    }
    parts.push(part);
    total += part.length;
  }

  return parts.join("\n\n");
}

function pickContextPages(pages: ScanPage[], prompt: string): ScanPage[] {
  const promptLower = normalizeText(prompt);
  const byPage = new Map<number, string>();
  for (const page of pages) {
    const pageNo = Number(page.page || 0);
    const text = cleanPageText(page);
    if (pageNo && text) byPage.set(pageNo, text);
  }

  const requested = extractPageNumbers(prompt);
  if (requested.length) {
    const selected: ScanPage[] = [];
    const seen = new Set<number>();
    const radius = requested.length === 1 && /(civar|yakın|yaklasik|yaklaşık)/i.test(prompt) ? 2 : (requested.length === 1 ? 1 : 0);
    for (const pageNo of requested) appendPageWindow(selected, seen, byPage, pageNo, radius);
    return selected.slice(0, MAX_CONTEXT_PAGES);
  }

  const terms = queryTerms(prompt).slice(0, 12);
  const scored: Array<{ score: number; page: number; text: string }> = [];
  for (const [pageNo, text] of byPage) {
    const lower = normalizeText(text);
    let score = 0;
    if (promptLower && lower.includes(promptLower)) score += 20;
    for (const term of terms) {
      const hits = lower.split(term).length - 1;
      if (hits > 0) score += Math.min(hits, 5) * 3;
    }
    if (score > 0) scored.push({ score, page: pageNo, text });
  }

  scored.sort((a, b) => b.score - a.score || a.page - b.page);
  return scored.slice(0, MAX_CONTEXT_PAGES).sort((a, b) => a.page - b.page).map((item) => ({
    page: item.page,
    text: item.text
  }));
}

function appendPageWindow(target: ScanPage[], seen: Set<number>, byPage: Map<number, string>, center: number, radius: number): void {
  for (let pageNo = center - radius; pageNo <= center + radius; pageNo += 1) {
    const text = byPage.get(pageNo);
    if (text && !seen.has(pageNo)) {
      target.push({ page: pageNo, text });
      seen.add(pageNo);
    }
  }
}

function extractPageNumbers(prompt: string): number[] {
  const textValue = prompt.toLowerCase();
  const found: number[] = [];
  for (const match of textValue.matchAll(/sayfa\s*(\d{1,4})\s*[-–]\s*(\d{1,4})/g)) {
    const start = Number(match[1]);
    const end = Number(match[2]);
    for (let page = Math.min(start, end); page <= Math.max(start, end); page += 1) found.push(page);
  }
  for (const match of textValue.matchAll(/(?:sayfa|sf)\s*(\d{1,4})/g)) found.push(Number(match[1]));
  for (const match of textValue.matchAll(/(\d{1,4})\.?\s*(?:sayfa|sf)\w*/g)) found.push(Number(match[1]));
  return [...new Set(found)].filter((page) => page > 0 && page < 2000);
}

function queryTerms(prompt: string): string[] {
  const stop = new Set(["için", "icin", "olan", "bana", "şunu", "sunu", "bunu", "nedir", "nasıl", "nasil", "sayfa", "soru", "cevap", "lütfen", "lutfen"]);
  return normalizeText(prompt)
    .split(/[^a-z0-9ığüşöçİĞÜŞÖÇ]+/i)
    .map((term) => term.trim())
    .filter((term) => term.length >= 3 && !stop.has(term));
}

function smallTalkResponse(prompt: string): string {
  const clean = normalizeText(prompt);
  if (/^(selam|merhaba|mrb|slm|sa|hey|hi|hello)\b/.test(clean)) {
    return "Merhaba, buradayım. Kitaptaki bir soru, sayfa veya konuyu yaz; hemen yardımcı olayım.";
  }
  if (clean.includes("teşekkür") || clean.includes("tesekkur") || clean.includes("sağ ol") || clean.includes("sag ol")) {
    return "Rica ederim. Buradayım; kitapla ilgili bir soru, sayfa veya konu yazarsan hemen yardımcı olurum.";
  }
  if (clean.includes("kimsin") || clean.includes("sen nesin") || clean.includes("adın ne") || clean.includes("adin ne")) {
    return "Ben ReylAI. Ders kitaplarındaki sayfa, soru ve konuları hızlıca açıklamak için buradayım.";
  }
  return "";
}

function buildHistoryContext(history: Array<{ role?: string; text?: string }>): string {
  return history.slice(-10).map((item) => {
    const role = item.role === "user" ? "Kullanıcı" : "ReylAI";
    const textValue = String(item.text || "").replace(/\s+/g, " ").trim().slice(0, 1800);
    return textValue ? `${role}: ${textValue}` : "";
  }).filter(Boolean).join("\n");
}

function fallbackChatTitle(prompt: string): string {
  return cleanChatTitle(prompt) || "Yeni sohbet";
}

function cleanChatTitle(title: string): string {
  let clean = title.replace(/[`*_>#[\]()"“”‘’]+/g, " ").replace(/\s+/g, " ").trim().replace(/[.:-]+$/g, "");
  if (clean.length > 64) clean = clean.slice(0, 61).trimEnd() + "...";
  return clean;
}

function findBook(library: Book[], selectedId: string): Book | undefined {
  return library.find((book) => book.book_id === selectedId) || library.find((book) => book.drive_id === selectedId);
}

function scanKeysForBook(book: Book | undefined, selectedId: string): string[] {
  return [selectedId, book?.book_id || "", book?.drive_id || ""].filter((value, index, arr) => value && arr.indexOf(value) === index);
}

function isBook(value: unknown): value is Book {
  return isRecord(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function cleanPageText(page: ScanPage): string {
  return String(page.text || "").trim();
}

function normalizeText(value: string): string {
  return value.toLocaleLowerCase("tr-TR").replace(/\s+/g, " ").trim();
}

function publicScanExtractor(extractor: string): string {
  return extractor.toLowerCase() === "adobe" ? "pypdf" : extractor;
}

function firstValidUrl(...values: Array<string | undefined>): string {
  for (const value of values) {
    const url = String(value || "").trim();
    if (/^https?:\/\/.+\.pdf($|[?#])/i.test(url)) return url;
  }
  return "";
}

function staticUrl(env: Env, path: string): string {
  return new URL(path, ensureSlash(env.STATIC_ORIGIN || "https://ai.reyliar.xyz")).toString();
}

function ensureSlash(url: string): string {
  return url.endsWith("/") ? url : `${url}/`;
}

function safeId(value: string): string {
  const trimmed = String(value || "").trim();
  return VALID_ID.test(trimmed) ? trimmed : "";
}

async function readJson<T>(request: Request): Promise<T> {
  try {
    return await request.json() as T;
  } catch {
    return {} as T;
  }
}

async function readTextSnippet(response: Response, limit: number): Promise<string> {
  if (!response.body) return "";
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let output = "";
  try {
    while (output.length < limit) {
      const chunk = await reader.read();
      if (chunk.done) break;
      output += decoder.decode(chunk.value, { stream: true });
      if (output.length >= limit) {
        await reader.cancel();
        break;
      }
    }
    output += decoder.decode();
  } finally {
    reader.releaseLock();
  }
  return output.slice(0, limit);
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: JSON_HEADERS
  });
}

function text(data: string, status = 200): Response {
  return new Response(data, {
    status,
    headers: TEXT_HEADERS
  });
}

function corsHeaders(request: Request): Headers {
  const headers = new Headers();
  const origin = request.headers.get("origin");
  headers.set("access-control-allow-origin", origin || "*");
  headers.set("access-control-allow-methods", "GET,POST,PUT,DELETE,OPTIONS");
  headers.set("access-control-allow-headers", "content-type,x-auth-token");
  headers.set("access-control-max-age", "86400");
  return headers;
}
