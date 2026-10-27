// スマホへの通知（Web Push）。鍵は最初に使うときに作って D1 にしまう。中身は暗号化して送る（RFC 8291 / 8292）
const SITE = "https://uchinoko.pocket-app.workers.dev";
const enc = new TextEncoder();
const b64u = (u8) => btoa(String.fromCharCode(...new Uint8Array(u8))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
const cat = (...a) => {
  const o = new Uint8Array(a.reduce((n, x) => n + x.length, 0));
  let i = 0;
  for (const x of a) { o.set(x, i); i += x.length; }
  return o;
};

export async function pushInit(db) {
  await db.exec("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL)");
  await db.exec("CREATE TABLE IF NOT EXISTS push (dev TEXT PRIMARY KEY, sub TEXT NOT NULL, fam TEXT, who TEXT, prefs TEXT, updated INTEGER NOT NULL)");
  await db.exec("CREATE TABLE IF NOT EXISTS pushq (id INTEGER PRIMARY KEY AUTOINCREMENT, dev TEXT NOT NULL, at INTEGER NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, url TEXT)");
  await db.exec("CREATE INDEX IF NOT EXISTS pushq_at ON pushq (at)");
}

let vapid = null;
async function keys(db) {
  if (vapid) return vapid;
  let row = await db.prepare("SELECT v FROM kv WHERE k = 'vapid'").first();
  if (!row) {
    const kp = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
    const jwk = await crypto.subtle.exportKey("jwk", kp.privateKey);
    const pub = b64u(await crypto.subtle.exportKey("raw", kp.publicKey));
    await db.prepare("INSERT OR IGNORE INTO kv (k, v) VALUES ('vapid', ?)").bind(JSON.stringify({ jwk, pub })).run();
    row = await db.prepare("SELECT v FROM kv WHERE k = 'vapid'").first();
  }
  const v = JSON.parse(row.v);
  vapid = { pub: v.pub, priv: await crypto.subtle.importKey("jwk", v.jwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]) };
  return vapid;
}

async function jwt(k, aud) {
  const h = b64u(enc.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const c = b64u(enc.encode(JSON.stringify({ aud, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: SITE })));
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, k.priv, enc.encode(h + "." + c));
  return h + "." + c + "." + b64u(sig);
}

async function hkdf(salt, ikm, info, len) {
  const k = await crypto.subtle.importKey("raw", ikm, "HKDF", false, ["deriveBits"]);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: "HKDF", hash: "SHA-256", salt, info }, k, len * 8));
}

// 中身を相手のスマホだけが読めるように包む（aes128gcm）
export async function encrypt(sub, text) {
  const ua = unb64u(sub.keys.p256dh), auth = unb64u(sub.keys.auth);
  const kp = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const as = new Uint8Array(await crypto.subtle.exportKey("raw", kp.publicKey));
  const uaKey = await crypto.subtle.importKey("raw", ua, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: uaKey }, kp.privateKey, 256));
  const ikm = await hkdf(auth, shared, cat(enc.encode("WebPush: info\0"), ua, as), 32);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(salt, ikm, enc.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdf(salt, ikm, enc.encode("Content-Encoding: nonce\0"), 12);
  const key = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["encrypt"]);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, key, cat(enc.encode(text), new Uint8Array([2]))));
  const rs = new Uint8Array([0, 0, 16, 0]);
  return cat(salt, rs, new Uint8Array([as.length]), as, ct);
}

// 送る。届かなくなった登録は消す
export async function send(env, dev, subJson, msg) {
  const sub = JSON.parse(subJson);
  const k = await keys(env.DB);
  const u = new URL(sub.endpoint);
  const r = await fetch(sub.endpoint, {
    method: "POST",
    headers: {
      authorization: `vapid t=${await jwt(k, u.origin)}, k=${k.pub}`,
      "content-encoding": "aes128gcm",
      "content-type": "application/octet-stream",
      ttl: "86400",
      urgency: "normal",
    },
    body: await encrypt(sub, JSON.stringify(msg)),
  });
  if (r.status === 404 || r.status === 410) {
    await env.DB.prepare("DELETE FROM push WHERE dev = ?").bind(dev).run();
    await env.DB.prepare("DELETE FROM pushq WHERE dev = ?").bind(dev).run();
  }
  return r.status;
}

const okDev = (d) => /^[0-9a-f]{24}$/.test(String(d || ""));
const okSub = (s) => s && typeof s.endpoint === "string" && /^https:\/\//.test(s.endpoint) && s.endpoint.length < 1000 && s.keys && s.keys.p256dh && s.keys.auth;
const clip = (t, n) => String(t || "").slice(0, n);

export async function pushKey(env) {
  await pushInit(env.DB);
  return (await keys(env.DB)).pub;
}

// 登録（famHash は合言葉をたしかめる関数）
export async function pushSub(env, b, famOk) {
  if (!okDev(b.dev) || !okSub(b.sub)) return { error: "bad" };
  const fam = b.fam && (await famOk(String(b.fam), String(b.code || ""))) ? String(b.fam) : null;
  await env.DB.prepare(
    "INSERT INTO push (dev, sub, fam, who, prefs, updated) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(dev) DO UPDATE SET sub = excluded.sub, fam = excluded.fam, who = excluded.who, prefs = excluded.prefs, updated = excluded.updated"
  ).bind(b.dev, JSON.stringify({ endpoint: b.sub.endpoint, keys: { p256dh: b.sub.keys.p256dh, auth: b.sub.keys.auth } }), fam, clip(b.who, 8), JSON.stringify(b.prefs || {}).slice(0, 500), Date.now()).run();
  return { ok: true, fam: !!fam };
}

export async function pushOff(env, b) {
  if (!okDev(b.dev)) return { error: "bad" };
  await env.DB.prepare("DELETE FROM push WHERE dev = ?").bind(b.dev).run();
  await env.DB.prepare("DELETE FROM pushq WHERE dev = ?").bind(b.dev).run();
  return { ok: true };
}

// このスマホで出す予定のお知らせを、まるごと入れかえる
export async function pushSched(env, b, famOk) {
  if (!okDev(b.dev) || !Array.isArray(b.items)) return { error: "bad" };
  const row = await env.DB.prepare("SELECT dev FROM push WHERE dev = ?").bind(b.dev).first();
  if (!row) return { error: "not_found" };
  const now = Date.now();
  const fam = b.fam && (await famOk(String(b.fam), String(b.code || ""))) ? String(b.fam) : null;
  const st = [
    env.DB.prepare("UPDATE push SET fam = ?, who = ?, prefs = ?, updated = ? WHERE dev = ?").bind(fam, clip(b.who, 8), JSON.stringify(b.prefs || {}).slice(0, 500), now, b.dev),
    env.DB.prepare("DELETE FROM pushq WHERE dev = ? AND kind = 's'").bind(b.dev),
  ];
  for (const it of b.items.slice(0, 150)) {
    const at = Number(it.at);
    if (!(at > now - 60_000 && at < now + 90 * 864e5)) continue;
    st.push(env.DB.prepare("INSERT INTO pushq (dev, at, kind, title, body, url) VALUES (?, ?, 's', ?, ?, ?)").bind(b.dev, at, clip(it.t, 60), clip(it.b, 160), clip(it.u, 60)));
  }
  await env.DB.batch(st);
  return { ok: true, n: st.length - 2 };
}

export async function pushTest(env, b) {
  if (!okDev(b.dev)) return { error: "bad" };
  const row = await env.DB.prepare("SELECT sub FROM push WHERE dev = ?").bind(b.dev).first();
  if (!row) return { error: "not_found" };
  const st = await send(env, b.dev, row.sub, { t: "うちの子手帳", b: "テストの通知です。これが見えていれば、通知は届きます。", u: "/" }).catch(() => 0);
  return { ok: st >= 200 && st < 300, status: st };
}

// パートナーが予定や買い物を足したら、同じ家族のほかのスマホへ
export async function pushPartner(env, fam, dev, oldData, put) {
  const subs = await env.DB.prepare("SELECT dev, sub, prefs FROM push WHERE fam = ? AND dev != ?").bind(fam, String(dev || "")).all();
  if (!subs.results.length) return;
  const me = okDev(dev) ? await env.DB.prepare("SELECT who FROM push WHERE dev = ?").bind(dev).first() : null;
  const who = (me && me.who) || "パートナー";
  const msgs = [];
  if (Array.isArray(put.plans)) {
    const old = new Set(((oldData.plans && oldData.plans.v) || []).map((p) => p.d + "|" + p.t));
    const add = put.plans.filter((p) => p && !old.has(p.d + "|" + p.t));
    if (add.length) msgs.push({ t: `${who}が予定を追加しました`, b: add.slice(0, 3).map((p) => `${String(p.d).slice(5).replace("-", "/")} ${clip(p.t, 40)}`).join("、") + (add.length > 3 ? ` ほか${add.length - 3}件` : ""), u: "/" });
  }
  if (Array.isArray(put.shop)) {
    const old = new Set(((oldData.shop && oldData.shop.v) || []).map((x) => x.t));
    const add = put.shop.filter((x) => x && !x.d && !old.has(x.t));
    if (add.length) msgs.push({ t: `${who}が買い物リストに追加しました`, b: add.slice(0, 4).map((x) => clip(x.t, 30)).join("、") + (add.length > 4 ? ` ほか${add.length - 4}件` : ""), u: "/" });
  }
  for (const s of subs.results) {
    let p = {};
    try { p = JSON.parse(s.prefs || "{}"); } catch (_) {}
    if (p.shop === false) continue;
    for (const m of msgs) await send(env, s.dev, s.sub, m).catch(() => {});
  }
}

// 15分ごと: 時間になったお知らせを送る
export async function pushCron(env) {
  await pushInit(env.DB);
  const now = Date.now();
  await env.DB.prepare("DELETE FROM pushq WHERE at < ?").bind(now - 6 * 3600_000).run();
  const r = await env.DB.prepare("SELECT q.id, q.dev, q.title, q.body, q.url, p.sub FROM pushq q JOIN push p ON p.dev = q.dev WHERE q.at <= ? ORDER BY q.at LIMIT 200").bind(now).all();
  for (const x of r.results) {
    await env.DB.prepare("DELETE FROM pushq WHERE id = ?").bind(x.id).run();
    await send(env, x.dev, x.sub, { t: x.title, b: x.body, u: x.url || "/" }).catch(() => {});
  }
}
