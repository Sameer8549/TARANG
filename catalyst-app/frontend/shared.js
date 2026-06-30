/* ═══════════════════════════════════════════════════
   TARANG — Shared JS
   Nav, Toast, WebSocket manager, TTS, API helpers
════════════════════════════════════════════════════ */
'use strict';

const T = window.TARANG = {};

T.API   = `${window.location.origin}/api`;
T.WS    = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/dashboard`;
T.SHORE = [12.8698, 74.8431];

/* ── Vessel & Type Maps ──────────────────────────── */
T.VESSEL_NAMES = {
  'VES-001':'Ananya Hegde','VES-002':'Kiran Shetty',
  'VES-003':'Meera Gowda','VES-004':'Prakash Naik','VES-005':'Nandini Rao'
};
T.VESSEL_OWNERS = {
  'VES-001':'Raghavendra Hegde','VES-002':'Savitha Shetty',
  'VES-003':'Basavaraj Gowda','VES-004':'Deepa Naik','VES-005':'Manjunath Rao'
};
T.VESSEL_POS = {
  'VES-001':[12.922,74.612],'VES-002':[12.794,74.832],
  'VES-003':[12.841,74.780],'VES-004':[12.885,74.710],'VES-005':[12.956,74.545]
};
T.TYPE_LABEL = {
  sos_manual:'Manual SOS Button',capsize:'Capsize Detected',
  drift:'Drift Anomaly',engine_fail:'Engine Failure',
  medical:'Medical Emergency',fire:'Fire on Vessel'
};
T.TYPE_ICON = {
  sos_manual:'🆘',capsize:'🌀',drift:'〰️',
  engine_fail:'⚙️',medical:'🏥',fire:'🔥'
};
T.SEV_COLOR = { critical:'#C0392B',high:'#C4521A',medium:'#B8860B',low:'#1E7A4E' };

/* ── Language Alert Texts ────────────────────────── */
T.LANG = {
  en: { code:'en-IN', label:'English',   flag:'🇬🇧' },
  kn: { code:'kn-IN', label:'ಕನ್ನಡ',       flag:'🇮🇳' },
  ml: { code:'ml-IN', label:'മലയാളം',     flag:'🇮🇳' },
  hi: { code:'hi-IN', label:'हिन्दी',      flag:'🇮🇳' },
  tu: { code:'kn-IN', label:'ತುಳು',        flag:'🇮🇳' },
};
T.ALERT_TEXTS = {
  en: (name, type, km) => `Emergency alert! Vessel ${name} has sent a ${type} distress signal, ${km} kilometers from shore. Immediate rescue action required.`,
  kn: (name, type, km) => `ತುರ್ತು ಎಚ್ಚರಿಕೆ! ದೋಣಿ ${name} ಅಪಾಯಕ್ಕೆ ಸಿಲುಕಿದೆ. ಕರಾವಳಿಯಿಂದ ${km} ಕಿಲೋಮೀಟರ್ ದೂರದಲ್ಲಿ ತುರ್ತು ಸಂಕೇತ ಕಳುಹಿಸಲಾಗಿದೆ. ತಕ್ಷಣ ರಕ್ಷಣಾ ಕಾರ್ಯಾಚರಣೆ ಅಗತ್ಯ.`,
  ml: (name, type, km) => `അടിയന്തര മുന്നറിയിപ്പ്! ബോട്ട് ${name} കടലിൽ അപകടത്തിൽ പെട്ടിരിക്കുന്നു. തീരത്തുനിന്ന് ${km} കിലോമീറ്റർ അകലെ. ഉടൻ രക്ഷാ നടപടി ആവശ്യം.`,
  hi: (name, type, km) => `आपातकालीन चेतावनी! नाव ${name} ने तट से ${km} किलोमीटर दूर संकट संकेत भेजा है। तत्काल बचाव कार्यवाही आवश्यक है।`,
  tu: (name, type, km) => `ತುರ್ತು ಸಂದೇಶ! ದೋಣಿ ${name} ಸಮಸ್ಯೆಲ್ ಉಂಡು. ${km} ಕಿಮೀ ದೂರದ ಕಡಲ್‍ಡ್ ಸಹಾಯ ಬೇಕು.`,
};

/* ── Toast ───────────────────────────────────────── */
T.toast = function(title, body, cls = '') {
  let c = document.getElementById('toast-container');
  if (!c) { c = document.createElement('div'); c.id = 'toast-container'; document.body.appendChild(c); }
  const el = document.createElement('div');
  el.className = `toast ${cls}`;
  el.innerHTML = `<div class="toast-title">${title}</div><div class="toast-body">${body}</div>`;
  c.appendChild(el);
  setTimeout(() => { el.style.opacity='0'; el.style.transform='translateX(110%)'; el.style.transition='all .3s'; setTimeout(()=>el.remove(),300); }, 5000);
};

/* ── Text-to-Speech ──────────────────────────────── */
T.speak = function(text, langCode = 'en-IN') {
  if (!window.speechSynthesis) { T.toast('TTS Unavailable', 'Your browser does not support speech synthesis.', ''); return; }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang  = langCode;
  u.rate  = 0.9;
  u.pitch = 1.0;
  u.volume= 1.0;
  const voices = window.speechSynthesis.getVoices();
  const match  = voices.find(v => v.lang === langCode || v.lang.startsWith(langCode.split('-')[0]));
  if (match) u.voice = match;
  window.speechSynthesis.speak(u);
};

T.speakAlert = function(alert, langKey = 'en') {
  const name = alert.vessel_name || T.VESSEL_NAMES[alert.vessel_id] || alert.vessel_id;
  const type = T.TYPE_LABEL[alert.alert_type] || alert.alert_type;
  const km   = alert.distance_km || '?';
  const text = T.ALERT_TEXTS[langKey] ? T.ALERT_TEXTS[langKey](name, type, km) : T.ALERT_TEXTS.en(name, type, km);
  const code = T.LANG[langKey]?.code || 'en-IN';
  T.speak(text, code);
};

/* ── WebSocket Manager ───────────────────────────── */
T.wsHandlers = [];
T.wsConnect  = function() {
  try {
    T._ws = new WebSocket(T.WS);
    T._ws.onopen    = () => T._wsBadge(true);
    T._ws.onclose   = () => { T._wsBadge(false); setTimeout(T.wsConnect, 3000); };
    T._ws.onerror   = () => T._ws.close();
    T._ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        T.wsHandlers.forEach(fn => fn(msg));
      } catch {}
    };
  } catch { T._wsBadge(false); }
};
T._wsBadge = function(on) {
  document.querySelectorAll('.nav-live').forEach(el => {
    el.className = 'nav-live ' + (on ? 'on' : 'off');
    const t = el.querySelector('span');
    if (t) t.textContent = on ? 'LIVE' : 'OFFLINE';
  });
};

/* ── API Helpers ─────────────────────────────────── */
T.getAlerts  = () => fetch(`${T.API}/alerts?limit=100`).then(r => r.json());
T.getVessels = () => fetch(`${T.API}/vessels`).then(r => r.json());
T.getWeather = () => fetch(`${T.API}/weather`).then(r => r.json());
T.postSOS    = (body) => fetch(`${T.API}/alerts/sos`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json());
T.simulateSOS= () => fetch(`${T.API}/simulate/sos`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.json());
T.dispatch   = (id, action) => fetch(`${T.API}/alerts/${id}/dispatch`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({alert_id:id,action,operator:'control_room'})}).then(r=>r.json());

/* ── Demo Alert Generator (offline) ─────────────── */
T._demoId = 1000;
T.makeDemoAlert = function(opts = {}) {
  const vids  = ['VES-001','VES-002','VES-003','VES-004','VES-005'];
  const types = ['sos_manual','capsize','drift','engine_fail','medical','fire'];
  const sevs  = ['critical','critical','high','high','medium','low'];
  const vid   = opts.vessel_id  || vids[Math.floor(Math.random()*vids.length)];
  const atype = opts.alert_type || types[Math.floor(Math.random()*types.length)];
  const sev   = opts.severity   || sevs[Math.floor(Math.random()*sevs.length)];
  const lat   = opts.lat || (12.72 + Math.random()*.34);
  const lng   = opts.lng || (74.50 + Math.random()*.46);
  const dlat  = lat - T.SHORE[0], dlng = lng - T.SHORE[1];
  const dist  = Math.sqrt(dlat*dlat*12100 + dlng*dlng*10000).toFixed(1);
  T._demoId++;
  return {
    id:           `ALT-D${T._demoId}`,
    alert_id:     `ALT-D${T._demoId}`,
    vessel_id:    vid,
    vessel_name:  T.VESSEL_NAMES[vid] || vid,
    lat, lng, alert_type: atype, severity: sev,
    status: opts.status || 'active',
    distance_km:  parseFloat(dist),
    weather_risk: 'moderate',
    hop_count:    opts.hop_count ?? Math.floor(Math.random()*3),
    battery_pct:  opts.battery_pct || Math.floor(60 + Math.random()*40),
    ai_summary:   `${T.VESSEL_NAMES[vid]} has triggered a ${T.TYPE_LABEL[atype] || atype} alert ${dist} km from Mangaluru shore. Severity assessed as ${sev.toUpperCase()}. Immediate Coast Guard response recommended. Weather conditions: moderate sea state, 1.4m wave height.`,
    ai_responder: parseFloat(dist) > 12 ? 'ICG Mangalore — FPV C-156 (ETA ~45 min)' : 'NDRF Coastal Unit — Mangaluru Harbour (ETA ~18 min)',
    created_at:   new Date().toISOString(),
  };
};

/* ── Nav clock ───────────────────────────────────── */
T.startClock = function(el) {
  if (!el) return;
  const tick = () => {
    el.textContent = new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'}) + ' IST';
  };
  tick(); setInterval(tick, 1000);
};

/* ── Render shared Nav ───────────────────────────── */
T.renderNav = function(active) {
  const pages = [
    { href:'/',               label:'Home'         },
    { href:'/dashboard',      label:'Dashboard'    },
    { href:'/how-it-works',   label:'How It Works' },
    { href:'/analytics',      label:'Analytics'    },
    { href:'/vessels',        label:'Vessels'      },
  ];
  const el = document.getElementById('nav');
  if (!el) return;
  el.innerHTML = `<div class="nav-inner">
    <div class="nav-brand">TARANG</div>
    <div class="nav-divider"></div>
    <nav class="nav-links">
      ${pages.map(p=>`<a class="nav-link${p.label===active?' active':''}" href="${p.href}">${p.label}</a>`).join('')}
    </nav>
    <div class="nav-right">
      <div class="nav-live off"><div class="nav-live-dot"></div><span>OFFLINE</span></div>
      <span id="nav-clock" class="mono" style="font-size:12px;color:var(--mist)"></span>
      <a href="/dashboard" class="nav-btn filled btn-sm btn">Control Room →</a>
    </div>
  </div>`;
  T.startClock(document.getElementById('nav-clock'));
};

/* ── Render shared Footer ────────────────────────── */
T.renderFooter = function() {
  const el = document.getElementById('footer');
  if (!el) return;
  el.innerHTML = `
  <div class="footer-inner">
    <div>
      <div class="footer-brand">TARANG</div>
      <p class="footer-desc">Coastal rescue operations dashboard for Coastal Innovation Hackathon, built by Deploy or Die.</p>
    </div>
    <div>
      <div class="footer-heading">Navigation</div>
      <ul class="footer-links">
        <li><a href="/">Home</a></li>
        <li><a href="/dashboard">Control Room</a></li>
        <li><a href="/demo">Live Demo</a></li>
        <li><a href="/analytics">Analytics</a></li>
        <li><a href="/vessels">Vessels</a></li>
        <li><a href="/docs">API Docs</a></li>
      </ul>
    </div>
    <div>
      <div class="footer-heading">Deploy or Die</div>
      <ul class="footer-links">
        <li><a href="#">Coastal Innovation Hackathon</a></li>
        <li><a href="#">Coastal Innovation Hackathon 2026</a></li>
        <li><a href="#">Bengaluru, Karnataka</a></li>
      </ul>
    </div>
  </div>
  <div class="footer-bar container">
    <span class="footer-copy">© 2026 Deploy or Die — Coastal Innovation Hackathon</span>
    <span class="footer-copy">TARANG v1.0 — SOS from the Sea</span>
  </div>`;
};
