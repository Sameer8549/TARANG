const http = require("http");
const https = require("https");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");
const crypto = require("crypto");

const PORT = Number(process.env.X_ZOHO_CATALYST_LISTEN_PORT || process.env.PORT || 9000);
const ROOT = __dirname;
const FRONTEND = path.join(ROOT, "frontend");
const wsClients = new Set();

function broadcast(type, data) {
  const payload = Buffer.from(JSON.stringify({ type, data }));
  const header = payload.length < 126
    ? Buffer.from([0x81, payload.length])
    : Buffer.from([0x81, 126, payload.length >> 8, payload.length & 255]);
  const frame = Buffer.concat([header, payload]);
  for (const socket of wsClients) {
    if (!socket.destroyed) socket.write(frame); else wsClients.delete(socket);
  }
}

let vessels = [
  { id: "VES-001", name: "Ananya Hegde", owner: "Raghavendra Hegde", status: "distress", lat: 12.8868, lng: 74.7761, battery_pct: 72 },
  { id: "VES-002", name: "Kiran Shetty", owner: "Savitha Shetty", status: "distress", lat: 12.9124, lng: 74.7428, battery_pct: 66 },
  { id: "VES-003", name: "Meera Gowda", owner: "Basavaraj Gowda", status: "distress", lat: 12.8421, lng: 74.8117, battery_pct: 81 },
  { id: "VES-004", name: "Prakash Naik", owner: "Deepa Naik", status: "distress", lat: 12.8019, lng: 74.7046, battery_pct: 58 },
  { id: "VES-005", name: "Nandini Rao", owner: "Manjunath Rao", status: "active", lat: 12.9542, lng: 74.6829, battery_pct: 89 },
  { id: "VES-006", name: "Shreyas Poojary", owner: "Leelavathi Poojary", status: "distress", lat: 12.9731, lng: 74.7312, battery_pct: 63 },
  { id: "VES-007", name: "Kavya Kotian", owner: "Ramesh Kotian", status: "distress", lat: 12.8248, lng: 74.7584, battery_pct: 77 },
  { id: "VES-008", name: "Naveen Kharvi", owner: "Geetha Kharvi", status: "active", lat: 12.7682, lng: 74.7925, battery_pct: 91 }
];

let alerts = [
  alert("ALT-001", "VES-001", "medical_emergency", "critical", 36.8, 670),
  alert("ALT-002", "VES-002", "engine_failure", "critical", 33.01, 676),
  alert("ALT-003", "VES-003", "engine_failure", "critical", 27.53, 1104),
  alert("ALT-004", "VES-004", "capsize", "critical", 24.53, 1144),
  alert("ALT-005", "VES-006", "navigation_failure", "high", 21.4, 42),
  alert("ALT-006", "VES-007", "medical_emergency", "high", 18.7, 18)
];

// Restore the complete pre-deployment SQLite snapshot (31 active, 7 dispatched, 8 resolved).
try {
  const legacy = JSON.parse(fs.readFileSync(path.join(ROOT, "legacy-data.json"), "utf8"));
  if (Array.isArray(legacy.vessels) && legacy.vessels.length) vessels = legacy.vessels;
  if (Array.isArray(legacy.alerts) && legacy.alerts.length) {
    alerts = legacy.alerts.map((item, index) => ({
      ...item,
      alert_id: item.id,
      timestamp: item.created_at,
      vessel_name: item.vessel_name || `Coastal profile ${index + 1}`,
      triage: {
        severity: item.severity,
        distance_km: item.distance_km,
        summary: item.ai_summary,
        ai_responder: item.ai_responder,
        weather_risk: item.weather_risk
      }
    }));
  }
} catch (error) {
  console.warn("Legacy database snapshot unavailable; using emergency seed data.");
}

function alert(id, vesselId, type, severity, distance, minutesAgo) {
  const v = vessels.find((x) => x.id === vesselId);
  const now = Date.now() - minutesAgo * 60000;
  return {
    id, alert_id: id, vessel_id: vesselId, vessel_name: v.name, owner: v.owner,
    alert_type: type, status: "active", severity, distance_km: distance,
    lat: v.lat, lng: v.lng, battery_pct: v.battery_pct, timestamp: new Date(now).toISOString(),
    ai_summary: `${v.name} requires immediate rescue coordination near the Mangaluru coast.`,
    ai_responder: "Coast Guard rescue vessel", weather_risk: "moderate",
    triage: { severity, distance_km: distance, summary: `${v.name} requires immediate rescue coordination.`, ai_responder: "Coast Guard rescue vessel", weather_risk: "moderate" }
  };
}

function send(res, code, body, type = "application/json") {
  const data = Buffer.isBuffer(body) ? body : type === "application/json" ? Buffer.from(JSON.stringify(body)) : Buffer.from(String(body));
  res.writeHead(code, { "content-type": type, "content-length": data.length, "access-control-allow-origin": "*" });
  res.end(data);
}

function readBody(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => { data += c; });
    req.on("end", () => {
      try { resolve(data ? JSON.parse(data) : {}); } catch { resolve({}); }
    });
  });
}

function requestJson(url, payload, headers = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const body = JSON.stringify(payload);
    const req = https.request({
      hostname: u.hostname, path: u.pathname + u.search, method: "POST",
      headers: { "content-type": "application/json", "content-length": Buffer.byteLength(body), ...headers }
    }, (res) => {
      let data = "";
      res.on("data", (c) => { data += c; });
      res.on("end", () => {
        try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
      });
    });
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

async function aiTriage(input) {
  const prompt = `Return JSON only for maritime SOS triage: ${JSON.stringify(input)}`;
  try {
    if (process.env.GROQ_API_KEY) {
      const r = await requestJson("https://api.groq.com/openai/v1/chat/completions", {
        model: "llama-3.1-8b-instant",
        messages: [{ role: "system", content: "Return valid compact JSON only." }, { role: "user", content: prompt }],
        temperature: 0.2
      }, { authorization: `Bearer ${process.env.GROQ_API_KEY}` });
      return JSON.parse(r.choices[0].message.content);
    }
    if (process.env.MISTRAL_API_KEY) {
      const r = await requestJson("https://api.mistral.ai/v1/chat/completions", {
        model: "mistral-small-latest",
        messages: [{ role: "user", content: prompt }],
        temperature: 0.2
      }, { authorization: `Bearer ${process.env.MISTRAL_API_KEY}` });
      return JSON.parse(r.choices[0].message.content);
    }
  } catch {}
  return { severity: "critical", summary: "Critical maritime distress. Dispatch rescue vessel and notify station.", ai_responder: "Coast Guard rescue vessel", weather_risk: "moderate", distance_km: input.distance_km || 24 };
}

function serveFile(res, file) {
  const ext = path.extname(file).toLowerCase();
  const types = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "application/javascript", ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".wav": "audio/wav", ".mp3": "audio/mpeg" };
  fs.readFile(file, (err, data) => err ? send(res, 404, "Not found", "text/plain") : send(res, 200, data, types[ext] || "application/octet-stream"));
}

async function handleApi(req, res, url) {
  if (req.method === "OPTIONS") return send(res, 204, "");
  if (url.pathname === "/health") return send(res, 200, { status: "ok", service: "TARANG", backend: "node-appsail", timestamp: new Date().toISOString() });
  if (url.pathname === "/api/vessels") return send(res, 200, vessels);
  const vesselMatch = url.pathname.match(/^\/api\/vessels\/([^/]+)$/);
  if (vesselMatch && req.method === "GET") {
    const vessel = vessels.find(v => v.id === vesselMatch[1]);
    return vessel ? send(res, 200, vessel) : send(res, 404, { error: "vessel not found" });
  }
  const positionMatch = url.pathname.match(/^\/api\/vessels\/([^/]+)\/position$/);
  if (positionMatch && req.method === "PATCH") {
    const body = await readBody(req);
    const vessel = vessels.find(v => v.id === positionMatch[1]);
    if (!vessel) return send(res, 404, { error: "vessel not found" });
    vessel.lat = Number(body.lat); vessel.lng = Number(body.lng); vessel.last_seen = new Date().toISOString();
    broadcast("vessel_update", vessel);
    return send(res, 200, { success: true, vessel_id: vessel.id });
  }
  if (url.pathname === "/api/weather") return send(res, 200, { source: "Open-Meteo Marine", wave_height_m: 1.4, wind_speed_ms: 6.1, visibility_m: 8000, risk: "moderate" });
  if (url.pathname === "/api/alerts") {
    const status = url.searchParams.get("status");
    const rows = status ? alerts.filter(a => a.status === status) : alerts;
    return send(res, 200, rows.slice(0, Number(url.searchParams.get("limit") || 100)));
  }
  const alertMatch = url.pathname.match(/^\/api\/alerts\/([^/]+)$/);
  if (alertMatch && req.method === "GET") {
    const item = alerts.find(a => a.id === alertMatch[1] || a.alert_id === alertMatch[1]);
    return item ? send(res, 200, { ...item, mesh_hops: item.mesh_hops || [] }) : send(res, 404, { error: "alert not found" });
  }
  if (url.pathname === "/api/ops/readiness") return send(res, 200, {
    station: "Mangaluru Station", ready: true, team: "Deploy or Die", vessels: vessels.length,
    active_alerts: alerts.filter(a => a.status === "active").length,
    dispatched_alerts: alerts.filter(a => a.status === "dispatched").length,
    resolved_alerts: alerts.filter(a => a.status === "resolved").length
  });
  if (url.pathname === "/api/ops/playbook") return send(res, 200, { steps: ["Locate vessel", "Dispatch rescue", "Notify family", "Resolve case"], team: "Deploy or Die" });
  if (url.pathname === "/api/simulate/sos" && req.method === "POST") {
    const v = vessels[Math.floor(Math.random() * vessels.length)];
    const triage = await aiTriage({ vessel: v.name, distance_km: 18 });
    const a = alert(`ALT-${Date.now()}`, v.id, "sos_manual", triage.severity || "critical", triage.distance_km || 18, 0);
    a.triage = { ...a.triage, ...triage };
    a.ai_summary = a.triage.summary;
    alerts.unshift(a);
    broadcast("new_alert", a);
    return send(res, 200, { ok: true, result: a });
  }
  if (url.pathname === "/api/alerts/sos" && req.method === "POST") {
    const body = await readBody(req);
    let vessel = vessels.find(v => v.id === body.vessel_id);
    if (!vessel) {
      vessel = { id: body.vessel_id || `VES-${Date.now()}`, name: `Unknown-${body.vessel_id || "vessel"}`, owner: "Unregistered", status: "distress", lat: Number(body.lat), lng: Number(body.lng), battery_pct: Number(body.battery_pct || 50) };
      vessels.push(vessel);
    }
    vessel.lat = Number(body.lat); vessel.lng = Number(body.lng); vessel.status = "distress";
    const triage = await aiTriage({ vessel: vessel.name, alert_type: body.alert_type, distance_km: body.distance_km || 20 });
    const item = alert(`ALT-${Date.now()}`, vessel.id, body.alert_type || "sos_manual", triage.severity || "critical", triage.distance_km || 20, 0);
    item.triage = { ...item.triage, ...triage }; item.ai_summary = item.triage.summary;
    alerts.unshift(item); broadcast("new_alert", item);
    return send(res, 200, { success: true, alert_id: item.id, triage: item.triage });
  }
  const dispatchMatch = url.pathname.match(/^\/api\/alerts\/([^/]+)\/dispatch$/);
  if (dispatchMatch && req.method === "PATCH") {
    const body = await readBody(req);
    const a = alerts.find((x) => x.id === dispatchMatch[1] || x.alert_id === dispatchMatch[1]);
    if (!a) return send(res, 404, { error: "alert not found" });
    if (body.action === "resolve") a.status = "resolved";
    else if (body.action && body.action.startsWith("dispatch")) a.status = "dispatched";
    if (a.status === "resolved") a.resolved_at = new Date().toISOString();
    broadcast("alert_update", { alert_id: a.id, status: a.status, action: body.action, operator: body.operator || "control_room" });
    return send(res, 200, { success: true, alert_id: a.id, new_status: a.status, alert: a });
  }
  if (url.pathname === "/api/voice/tts" && req.method === "POST") {
    const body = await readBody(req);
    const lang = body.lang === "kn" ? "kn" : "en";
    const text = encodeURIComponent((body.text || "Emergency alert").slice(0, 180));
    https.get(`https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=${lang}&q=${text}`, (r) => {
      const chunks = [];
      r.on("data", (c) => chunks.push(c));
      r.on("end", () => send(res, 200, Buffer.concat(chunks), "audio/mpeg"));
    }).on("error", () => send(res, 500, { error: "tts failed" }));
    return;
  }
  return send(res, 404, { error: "not found" });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname === "/health" || url.pathname.startsWith("/api/")) return handleApi(req, res, url);
  const routes = { "/": "app.html", "/dashboard": "dashboard.html", "/how-it-works": "how-it-works.html", "/analytics": "analytics.html", "/vessels": "vessels.html" };
  const relative = routes[url.pathname] || url.pathname.replace(/^\/static\//, "").replace(/^\//, "");
  const file = path.normalize(path.join(FRONTEND, relative));
  if (!file.startsWith(FRONTEND)) return send(res, 403, "Forbidden", "text/plain");
  serveFile(res, file);
});
server.on("upgrade", (req, socket) => {
  if (req.url !== "/ws/dashboard" || !req.headers["sec-websocket-key"]) return socket.destroy();
  const accept = crypto.createHash("sha1").update(req.headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest("base64");
  socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
  wsClients.add(socket);
  socket.on("close", () => wsClients.delete(socket));
  socket.on("error", () => wsClients.delete(socket));
});
server.listen(PORT, "0.0.0.0", () => {
  console.log(`TARANG AppSail backend listening on ${PORT}`);
});
