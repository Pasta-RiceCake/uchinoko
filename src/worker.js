import { pushInit, pushKey, pushSub, pushOff, pushSched, pushTest, pushPartner, pushCron } from "./push.js";
// うちの子手帳: ふたりの共有データを D1 に置くだけの小さな API。
// それ以外（画面）は public/ の静的ファイルをそのまま返す。

const MAX_BODY = 1_500_000;
const LOCK_FAILS = 10;
const LOCK_MS = 60 * 60 * 1000;

let ready = false;
async function init(db) {
  if (ready) return;
  await db.exec(
    "CREATE TABLE IF NOT EXISTS fam (id TEXT PRIMARY KEY, code TEXT NOT NULL, data TEXT NOT NULL, rev INTEGER NOT NULL, fails INTEGER NOT NULL DEFAULT 0, fail_at INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL, updated INTEGER NOT NULL)"
  );
  await db.exec("CREATE TABLE IF NOT EXISTS move (code TEXT PRIMARY KEY, data TEXT NOT NULL, exp INTEGER NOT NULL)");
  await db.exec("CREATE TABLE IF NOT EXISTS icon (id TEXT PRIMARY KEY, png BLOB NOT NULL, created INTEGER NOT NULL)");
  // スマホごとのホーム画面アイコン（Android はここを見て、アイコンを新しくする）
  await db.exec("CREATE TABLE IF NOT EXISTS appman (mid TEXT PRIMARY KEY, icon TEXT NOT NULL, updated INTEGER NOT NULL)");
  // 共有していない人の市区町村も、イベント・サービスを読む対象にする（市の名前だけ。誰かはわからない）
  await db.exec("CREATE TABLE IF NOT EXISTS citywant (city TEXT PRIMARY KEY, seen INTEGER NOT NULL)");
  await pushInit(db);
  ready = true;
}

const json = (o, status = 200) =>
  new Response(JSON.stringify(o), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });

async function hash(id, code) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(id + ":" + code));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

function randId() {
  const a = "abcdefghijkmnpqrstuvwxyz23456789";
  const r = crypto.getRandomValues(new Uint8Array(10));
  return [...r].map((x) => a[x % a.length]).join("");
}
function randCode() {
  const r = crypto.getRandomValues(new Uint32Array(1))[0];
  return String(r % 1_000_000).padStart(6, "0");
}

async function readBody(req) {
  const t = await req.text();
  if (t.length > MAX_BODY) throw new Error("too_big");
  return t ? JSON.parse(t) : {};
}

// put: { key: value } をサーバー側の rev で記録する
function merge(data, put, rev) {
  for (const k of Object.keys(put || {})) {
    if (k.length > 40) continue;
    data[k] = { v: put[k], r: rev };
  }
}

async function create(req, env) {
  const b = await readBody(req);
  const now = Date.now();
  for (let n = 0; n < 5; n++) {
    const id = randId(), code = randCode(), data = {};
    merge(data, b.put, 1);
    try {
      await env.DB.prepare("INSERT INTO fam (id, code, data, rev, created, updated) VALUES (?, ?, ?, 1, ?, ?)")
        .bind(id, await hash(id, code), JSON.stringify(data), now, now)
        .run();
      return json({ id, code, rev: 1 });
    } catch (e) {
      if (!String(e).includes("UNIQUE")) throw e;
    }
  }
  return json({ error: "retry" }, 500);
}

async function sync(req, env, id, ctx) {
  const b = await readBody(req);
  const row = await env.DB.prepare("SELECT * FROM fam WHERE id = ?").bind(id).first();
  if (!row) return json({ error: "not_found" }, 404);
  const now = Date.now();
  if (row.fails >= LOCK_FAILS && now - row.fail_at < LOCK_MS) return json({ error: "locked" }, 429);
  if ((await hash(id, String(b.code || ""))) !== row.code) {
    const fails = now - row.fail_at < LOCK_MS ? row.fails + 1 : 1;
    await env.DB.prepare("UPDATE fam SET fails = ?, fail_at = ? WHERE id = ?").bind(fails, now, id).run();
    return json({ error: "bad_code" }, 403);
  }
  if (row.fails) await env.DB.prepare("UPDATE fam SET fails = 0 WHERE id = ?").bind(id).run();

  const since = Number(b.rev) || 0;
  const put = b.put && typeof b.put === "object" ? b.put : {};
  let cur = row;
  // 同時に書きこまれたときは rev を見てやり直す
  for (let n = 0; n < 4; n++) {
    const data = JSON.parse(cur.data);
    let rev = cur.rev;
    if (Object.keys(put).length) {
      rev = cur.rev + 1;
      merge(data, put, rev);
      const r = await env.DB.prepare("UPDATE fam SET data = ?, rev = ?, updated = ? WHERE id = ? AND rev = ?")
        .bind(JSON.stringify(data), rev, now, id, cur.rev)
        .run();
      if (!r.meta.changes) {
        cur = await env.DB.prepare("SELECT * FROM fam WHERE id = ?").bind(id).first();
        continue;
      }
    }
    if (ctx && (put.plans || put.shop)) ctx.waitUntil(pushPartner(env, id, b.dev, JSON.parse(cur.data), put).catch(() => {}));
    const upd = {};
    for (const k of Object.keys(data)) if (data[k].r > since && !(k in put)) upd[k] = data[k].v;
    return json({ rev, upd });
  }
  return json({ error: "busy" }, 503);
}

// 機種変更の引き継ぎ: 24時間だけ使える1回きりのコード
const MOVE_MS = 24 * 60 * 60 * 1000;
function moveCode() {
  const a = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const r = crypto.getRandomValues(new Uint8Array(8));
  return [...r].map((x) => a[x % a.length]).join("");
}
async function movePut(req, env) {
  const b = await readBody(req);
  if (!b.data || typeof b.data !== "object") return json({ error: "bad" }, 400);
  const now = Date.now();
  await env.DB.prepare("DELETE FROM move WHERE exp < ?").bind(now).run();
  const code = moveCode();
  await env.DB.prepare("INSERT INTO move (code, data, exp) VALUES (?, ?, ?)").bind(code, JSON.stringify(b.data), now + MOVE_MS).run();
  return json({ code, exp: now + MOVE_MS });
}
async function moveGet(req, env) {
  const b = await readBody(req);
  const code = String(b.code || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  const row = await env.DB.prepare("SELECT * FROM move WHERE code = ? AND exp > ?").bind(code, Date.now()).first();
  if (!row) return json({ error: "not_found" }, 404);
  await env.DB.prepare("DELETE FROM move WHERE code = ?").bind(code).run();
  return json({ data: JSON.parse(row.data) });
}

// ホーム画面のアイコン: 同じ画像は同じ id になる
async function iconPut(req, env) {
  const b = await readBody(req);
  const bin = Uint8Array.from(atob(String(b.png || "")), (c) => c.charCodeAt(0));
  if (bin.length < 100 || bin.length > 600_000 || bin[1] !== 0x50 || bin[2] !== 0x4e || bin[3] !== 0x47) return json({ error: "bad" }, 400);
  const h = await crypto.subtle.digest("SHA-256", bin);
  const id = [...new Uint8Array(h)].slice(0, 12).map((x) => x.toString(16).padStart(2, "0")).join("");
  await env.DB.prepare("INSERT OR IGNORE INTO icon (id, png, created) VALUES (?, ?, ?)").bind(id, bin, Date.now()).run();
  if (/^[0-9a-f]{24}$/.test(String(b.mid || "")))
    await env.DB.prepare("INSERT INTO appman (mid, icon, updated) VALUES (?, ?, ?) ON CONFLICT(mid) DO UPDATE SET icon = excluded.icon, updated = excluded.updated")
      .bind(b.mid, id, Date.now()).run();
  return json({ id });
}
async function iconGet(env, id) {
  await init(env.DB);
  const row = await env.DB.prepare("SELECT png FROM icon WHERE id = ?").bind(id).first();
  if (!row) return new Response("not found", { status: 404 });
  return new Response(new Uint8Array(row.png), { headers: { "content-type": "image/png", "cache-control": "public, max-age=31536000, immutable" } });
}
async function manifest(env, id, url) {
  if (id !== "default") {
    await init(env.DB);
    const row = await env.DB.prepare("SELECT icon FROM appman WHERE mid = ?").bind(id).first();
    if (row) id = row.icon;
  }
  const src = id === "default" ? "/icon-512.png" : "/i/" + id + ".png";
  const f = url.searchParams.get("f") || "";
  const start = /^[a-z0-9]{10}\.\d{6}$/.test(f) ? "/?f=" + f : "/";
  return new Response(
    JSON.stringify({
      name: "うちの子手帳", short_name: "うちの子手帳", lang: "ja", start_url: start, scope: "/", display: "standalone",
      background_color: "#fdf3f5", theme_color: "#f7e9ec",
      icons: [{ src, sizes: "512x512", type: "image/png", purpose: "any" }, { src, sizes: "512x512", type: "image/png", purpose: "maskable" }],
    }),
    { headers: { "content-type": "application/manifest+json; charset=utf-8", "cache-control": "no-store" } }
  );
}

// 子育てイベントを集める市区町村（家族のいる市だけ）。人数は出さない
async function cityWant(req, env) {
  const b = await req.json().catch(() => ({}));
  const p = String(b.p || ""), c = String(b.c || "").trim();
  if (!/^.{2,3}[都道府県]$/.test(p) || !c || c.length > 20) return new Response("bad", { status: 400 });
  await init(env.DB);
  await env.DB.prepare("INSERT INTO citywant (city, seen) VALUES (?, ?) ON CONFLICT(city) DO UPDATE SET seen = excluded.seen").bind(p + c, Date.now()).run();
  return new Response("ok");
}

async function cities(env) {
  await init(env.DB);
  const r = await env.DB.prepare(
    "SELECT DISTINCT json_extract(data, '$.pref.v') AS p, json_extract(data, '$.city.v') AS c FROM fam WHERE json_valid(data)"
  ).all();
  const list = r.results.filter((x) => x.p && x.c).map((x) => x.p + x.c);
  await env.DB.prepare("DELETE FROM citywant WHERE seen < ?").bind(Date.now() - 180 * 864e5).run();
  const w = await env.DB.prepare("SELECT city FROM citywant").all();
  for (const x of w.results) list.push(x.city);
  return new Response(JSON.stringify({ cities: [...new Set(list)].sort() }), {
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=3600" },
  });
}

// 家族のあいことばが合っているか
async function famOk(env, id, code) {
  const row = await env.DB.prepare("SELECT code FROM fam WHERE id = ?").bind(id).first();
  return !!row && row.code === (await hash(id, code));
}

export default {
  async scheduled(ev, env, ctx) {
    ctx.waitUntil(pushCron(env));
  },
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    let m = url.pathname.match(/^\/i\/([0-9a-f]{24})\.png$/);
    if (m) return await iconGet(env, m[1]);
    m = url.pathname.match(/^\/m\/([0-9a-f]{24}|default)\.webmanifest$/);
    if (m) return await manifest(env, m[1], url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(req);
    if (url.pathname === "/api/cities" && req.method === "GET") return await cities(env);
    if (url.pathname === "/api/city" && req.method === "POST") return await cityWant(req, env);
    if (url.pathname === "/api/push/key" && req.method === "GET") {
      await init(env.DB);
      return json({ k: await pushKey(env) });
    }
    if (req.method !== "POST") return json({ error: "method" }, 405);
    try {
      await init(env.DB);
      if (url.pathname === "/api/fam") return await create(req, env);
      if (url.pathname === "/api/icon") return await iconPut(req, env);
      if (url.pathname === "/api/move") return await movePut(req, env);
      if (url.pathname === "/api/move/get") return await moveGet(req, env);
      if (url.pathname === "/api/push/sub") return json(await pushSub(env, await readBody(req), (i, c) => famOk(env, i, c)));
      if (url.pathname === "/api/push/off") return json(await pushOff(env, await readBody(req)));
      if (url.pathname === "/api/push/sched") return json(await pushSched(env, await readBody(req), (i, c) => famOk(env, i, c)));
      if (url.pathname === "/api/push/test") return json(await pushTest(env, await readBody(req)));
      const m = url.pathname.match(/^\/api\/fam\/([a-z0-9]{10})\/sync$/);
      if (m) return await sync(req, env, m[1], ctx);
      return json({ error: "not_found" }, 404);
    } catch (e) {
      if (String(e.message) === "too_big") return json({ error: "too_big" }, 413);
      return json({ error: "server" }, 500);
    }
  },
};
