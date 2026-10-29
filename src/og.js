// お役立ちメモ：貼ったリンクから、題名・本文・サムネイルを取ってくる
// X・TikTok・YouTube は公式の埋め込み用の窓口（oEmbed）、ほかはページの og: タグを読む
// 取ったものはその人のスマホの中にだけ保存される（ここでは何も記録しない）
const UA = "Mozilla/5.0 (compatible; uchinoko-memo/1.0; +https://uchinoko.pocket-app.workers.dev/)";
const strip = (s) =>
  String(s || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#0?39;|&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n)).replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/[ \t]+\n/g, "\n").trim();
const meta = (h, k) => {
  const m = h.match(new RegExp(`<meta[^>]+(?:property|name)=["']${k}["'][^>]*>`, "i"));
  if (!m) return "";
  const c = m[0].match(/content=["']([^"']*)["']/i);
  return c ? strip(c[1]) : "";
};
async function get(u, opt = {}) {
  const r = await fetch(u, { headers: { "user-agent": opt.ua || UA, accept: opt.accept || "*/*", "accept-language": "ja,en;q=0.8" }, redirect: "follow", cf: { cacheTtl: 86400 } });
  if (!r.ok) throw new Error("fetch " + r.status);
  return r;
}
async function img(u) {
  if (!u || !/^https:\/\//.test(u)) return "";
  try {
    const r = await get(u, { accept: "image/*" });
    const t = r.headers.get("content-type") || "";
    if (!/^image\/(jpeg|png|webp|gif)/.test(t)) return "";
    const b = new Uint8Array(await r.arrayBuffer());
    if (b.length > 600000) return "";
    let s = "";
    for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode(...b.subarray(i, i + 0x8000));
    return "data:" + t.split(";")[0] + ";base64," + btoa(s);
  } catch (_) {
    return "";
  }
}
async function look(u) {
  const h = new URL(u).hostname.replace(/^(www|m|mobile|vm|vt)\./, "");
  if (/^(x|twitter)\.com$/.test(h)) {
    const j = await (await get("https://publish.twitter.com/oembed?omit_script=1&dnt=1&url=" + encodeURIComponent(u.replace("//x.com", "//twitter.com")))).json();
    const p = (j.html || "").match(/<p[^>]*>([\s\S]*?)<\/p>/);
    return { t: j.author_name ? j.author_name + "さんの投稿" : "", n: p ? strip(p[1].replace(/<a [^>]*>(pic\.twitter\.com[^<]*|https?:\/\/t\.co[^<]*)<\/a>/g, "")) : "", i: "" };
  }
  if (/tiktok\.com$/.test(h)) {
    const j = await (await get("https://www.tiktok.com/oembed?url=" + encodeURIComponent(u))).json();
    return { t: j.author_name ? j.author_name + "さんの動画" : "", n: strip(j.title), i: j.thumbnail_url };
  }
  if (/youtube\.com$|youtu\.be$/.test(h)) {
    const j = await (await get("https://www.youtube.com/oembed?format=json&url=" + encodeURIComponent(u))).json();
    return { t: strip(j.title), n: j.author_name ? j.author_name : "", i: j.thumbnail_url };
  }
  // インスタ・Threads・ブログなど：ページの og: タグ（インスタはログインが必要で取れないことも多い）
  const r = await get(u, { ua: /instagram|threads/.test(h) ? "facebookexternalhit/1.1" : UA, accept: "text/html" });
  const html = (await r.text()).slice(0, 300000);
  const t = meta(html, "og:title") || strip((html.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [])[1]);
  return { t, n: meta(html, "og:description") || meta(html, "description"), i: meta(html, "og:image") };
}
export async function og(url) {
  const u = url.searchParams.get("u") || "";
  let p;
  try {
    p = new URL(u);
  } catch (_) {
    return new Response('{"error":"bad"}', { status: 400 });
  }
  if (p.protocol !== "https:" || /^(localhost|[\d.]+|\[.*\])$/.test(p.hostname) || u.length > 600) return new Response('{"error":"bad"}', { status: 400 });
  let o = { t: "", n: "", i: "" };
  try {
    o = await look(u);
  } catch (_) {}
  const out = { t: (o.t || "").slice(0, 120), n: (o.n || "").slice(0, 3000), img: await img(o.i) };
  return new Response(JSON.stringify(out), { headers: { "content-type": "application/json; charset=utf-8", "cache-control": "private, max-age=3600" } });
}
