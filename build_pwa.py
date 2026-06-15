#!/usr/bin/env python3
"""改造日程助手HTML：添加Supabase云同步 + PWA支持"""
import re

HTML_PATH = "/Users/zzx/Desktop/咨询日程/咨询师日程助手.html"
MANIFEST_PATH = "/Users/zzx/Desktop/咨询日程/manifest.json"
SW_PATH = "/Users/zzx/Desktop/咨询日程/sw.js"

SUPABASE_URL = "https://qlszqstrmxofdtugxfbo.supabase.co"
SUPABASE_KEY = "sb_publishable_amUCZmB4e6Q5SDlQUxctNw_DQVK4riQ"

with open(HTML_PATH, 'r') as f:
    html = f.read()

# 1. 在</head>前添加Supabase SDK和PWA link
head_add = '''<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#4a7c65">
<script src="https://unpkg.com/@supabase/supabase-js@2"></script>
<style>
#loginOverlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.4);display:flex;justify-content:center;align-items:center;z-index:9999}
#loginBox{background:#fff;border-radius:16px;padding:32px;width:90%;max-width:360px;box-shadow:0 8px 40px rgba(0,0,0,0.15);text-align:center}
#loginBox h2{margin-bottom:8px;font-size:20px}
#loginBox p{color:#8b8578;font-size:13px;margin-bottom:20px}
#loginBox input{width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:8px;font-size:16px;text-align:center;margin-bottom:16px;font-family:inherit}
#loginBox button{width:100%;padding:10px;background:#4a7c65;color:#fff;border:none;border-radius:8px;font-size:15px;cursor:pointer}
#loginBox button:hover{background:#3d6b56}
#loginBox .hint{font-size:11px;color:#bbb;margin-top:12px}
#syncBanner{background:#eaf5ef;color:#4a7c65;padding:8px 16px;border-radius:8px;font-size:12px;margin-bottom:12px;display:none;align-items:center;justify-content:space-between}
#syncBanner button{padding:4px 12px;background:#4a7c65;color:#fff;border:none;border-radius:4px;font-size:11px;cursor:pointer}
</style>
</head>'''
html = html.replace('</head>', head_add)

# 2. 在<body>之后添加登录覆盖层
login_html = '''<div id="loginOverlay">
  <div id="loginBox">
    <h2>咨询师日程助手</h2>
    <p>输入你的访问码，登录后数据自动同步到云端</p>
    <input type="text" id="accessCodeInput" placeholder="输入访问码" autocomplete="off">
    <button onclick="login()">登录 / 注册</button>
    <div class="hint">首次输入任意码即可创建账号</div>
  </div>
</div>
<div id="syncBanner"><span id="syncStatus">⬆ 有本地数据待上传</span><button onclick="syncLocalToCloud()">上传到云端</button></div>'''
html = html.replace('<body>', '<body>\n' + login_html)

# 3. 在第一个<script>之前添加Supabase初始化和登录逻辑
supabase_js = '''
<script>
// ===== Supabase 初始化 =====
const { createClient } = supabase;
const _supabase = createClient("''' + SUPABASE_URL + '''", "''' + SUPABASE_KEY + '''");
var _accessCode = localStorage.getItem("counselor_access") || "";

async function login() {
  var code = document.getElementById("accessCodeInput").value.trim();
  if (!code) return alert("请输入访问码");
  _accessCode = code;
  localStorage.setItem("counselor_access", code);
  document.getElementById("loginOverlay").style.display = "none";
  await loadFromCloud();
  // 检查是否有本地数据需要迁移
  var local = JSON.parse(localStorage.getItem("counselor_appts") || "[]");
  if (local.length > 0 && local.some(function(a){ return !a._synced })) {
    document.getElementById("syncBanner").style.display = "flex";
  }
}

// 页面加载时检查是否已登录
(function(){
  var saved = localStorage.getItem("counselor_access");
  if (saved) {
    _accessCode = saved;
    document.getElementById("loginOverlay").style.display = "none";
    loadFromCloud();
  }
})();

async function loadFromCloud() {
  if (!_accessCode) return;
  try {
    var { data, error } = await _supabase
      .from("appointments")
      .select("*")
      .eq("access_code", _accessCode);
    if (error) throw error;
    if (data && data.length > 0) {
      // 转成appointments格式
      var cloud = data.map(function(r){ return {
        id: r.appt_id, name: r.client_name, date: r.date,
        start: r.time ? r.time.split("-")[0] : "09:00",
        end: r.time ? r.time.split("-")[1] : "09:50",
        type: r.type || "new", notes: r.notes || "",
        visitBase: 0, recurring: "none", _synced: true,
        createdAt: r.created_at
      };});
      // 合并云端和本地
      var local = JSON.parse(localStorage.getItem("counselor_appts") || "[]");
      var cloudIds = {}; cloud.forEach(function(a){ cloudIds[a.id] = true; });
      // 本地上传未同步的
      var unsynced = local.filter(function(a){ return !a._synced && !cloudIds[a.id]; });
      for (var i=0; i<unsynced.length; i++) {
        await saveToCloud(unsynced[i]);
      }
      appointments = cloud;
      localStorage.setItem("counselor_appts", JSON.stringify(appointments));
      renderGreeting(); renderDateStrip(); renderWeek();
    }
  } catch(e) { console.log("云同步失败，使用本地数据:", e.message); }
}

async function saveToCloud(appt) {
  try {
    var timeStr = (appt.start || "09:00") + "-" + (appt.end || "09:50");
    var { error } = await _supabase.from("appointments").upsert({
      access_code: _accessCode,
      appt_id: appt.id,
      date: appt.date,
      time: timeStr,
      client_name: appt.name || "",
      phone: "",
      type: appt.type || "new",
      notes: appt.notes || ""
    }, { onConflict: "appt_id" });
    if (error) throw error;
    appt._synced = true;
  } catch(e) { console.log("云端保存失败:", e.message); }
}

async function syncLocalToCloud() {
  var local = JSON.parse(localStorage.getItem("counselor_appts") || "[]");
  if (!local.length) { document.getElementById("syncBanner").style.display = "none"; return; }
  document.getElementById("syncStatus").textContent = "⏳ 上传中...";
  var count = 0;
  for (var i=0; i<local.length; i++) {
    if (!local[i]._synced) { await saveToCloud(local[i]); count++; }
  }
  localStorage.setItem("counselor_appts", JSON.stringify(local));
  document.getElementById("syncStatus").textContent = "✅ 已上传 " + count + " 条";
  setTimeout(function(){ document.getElementById("syncBanner").style.display = "none"; }, 2000);
}

// 重写save函数
var _origSave = save;
save = function() {
  _origSave();
  var a = appointments;
  localStorage.setItem("counselor_appts", JSON.stringify(a));
  if (_accessCode) {
    for (var i=0; i<a.length; i++) {
      if (!a[i]._synced) { saveToCloud(a[i]); }
    }
  }
};
</script>
'''
html = html.replace('<script>', supabase_js + '\n<script>')

# 4. 保存
with open(HTML_PATH, 'w') as f:
    f.write(html)
print(f"✅ HTML已更新: {HTML_PATH}")

# 5. manifest.json
manifest = {
    "name": "咨询师日程助手",
    "short_name": "日程助手",
    "start_url": ".",
    "display": "standalone",
    "background_color": "#ede9e2",
    "theme_color": "#4a7c65",
    "icons": [{"src": "icon_calendar.png", "sizes": "512x512", "type": "image/png"}]
}
import json
with open(MANIFEST_PATH, 'w') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"✅ manifest: {MANIFEST_PATH}")

# 6. sw.js
sw = '''const CACHE = "counselor-cal-v1";
const STATIC = [".", "icon_calendar.png", "manifest.json"];
self.addEventListener("install", function(e) {
  e.waitUntil(caches.open(CACHE).then(function(c) { return c.addAll(STATIC); }));
  self.skipWaiting();
});
self.addEventListener("fetch", function(e) {
  if (e.request.url.indexOf("supabase") > -1) {
    e.respondWith(networkFirst(e.request));
  } else {
    e.respondWith(cacheFirst(e.request));
  }
});
async function networkFirst(req) {
  try {
    var net = await fetch(req);
    var cache = await caches.open(CACHE);
    cache.put(req, net.clone());
    return net;
  } catch(e) { return caches.match(req); }
}
async function cacheFirst(req) {
  var hit = await caches.match(req);
  return hit || fetch(req);
}
self.addEventListener("activate", function(e) {
  e.waitUntil(clients.claim());
});'''
with open(SW_PATH, 'w') as f:
    f.write(sw)
print(f"✅ service worker: {SW_PATH}")
print("完成！打开页面后，输入访问码即可开始使用")
