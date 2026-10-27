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

async function sync(req, env, id) {
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
    const upd = {};
    for (const k of Object.keys(data)) if (data[k].r > since && !(k in put)) upd[k] = data[k].v;
    return json({ rev, upd });
  }
  return json({ error: "busy" }, 503);
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(req);
    if (req.method !== "POST") return json({ error: "method" }, 405);
    try {
      await init(env.DB);
      if (url.pathname === "/api/fam") return await create(req, env);
      const m = url.pathname.match(/^\/api\/fam\/([a-z0-9]{10})\/sync$/);
      if (m) return await sync(req, env, m[1]);
      return json({ error: "not_found" }, 404);
    } catch (e) {
      if (String(e.message) === "too_big") return json({ error: "too_big" }, 413);
      return json({ error: "server" }, 500);
    }
  },
};
