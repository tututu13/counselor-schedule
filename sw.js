const CACHE_NAME = "counselor-cal-v2";
const STATIC_ASSETS = [
  "咨询师日程助手.html",
  "icon_calendar.png",
  "icon_192.png",
  "icon_512.png",
  "manifest.json"
];

const SUPABASE_API = "https://qlszqstrmxofdtugxfbo.supabase.co";

// ===== Install: 预缓存静态资源 =====
self.addEventListener("install", function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      // 逐个缓存，单个失败不影响其他
      return Promise.allSettled(
        STATIC_ASSETS.map(function(url) {
          return cache.add(url).catch(function(err) {
            console.warn("[SW] 缓存失败:", url, err.message);
          });
        })
      );
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

// ===== Activate: 清理旧缓存 =====
self.addEventListener("activate", function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { return caches.delete(k); })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

// ===== Fetch: 策略分发 =====
self.addEventListener("fetch", function(event) {
  var url = event.request.url;

  // Supabase API 请求 → Network First
  if (url.indexOf(SUPABASE_API) === 0) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  // 同源静态资源 → Cache First
  if (url.startsWith(self.location.origin)) {
    event.respondWith(cacheFirst(event.request));
    return;
  }

  // 跨域资源（如 unpkg CDN）→ Network Only，不缓存
  return;
});

// ===== Network First 策略 =====
async function networkFirst(request) {
  try {
    var response = await fetch(request);
    if (response && response.status === 200) {
      var cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    var cached = await caches.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ error: "离线，无法连接服务器" }), {
      status: 503,
      headers: { "Content-Type": "application/json" }
    });
  }
}

// ===== Cache First 策略 =====
async function cacheFirst(request) {
  var cached = await caches.match(request);
  if (cached) return cached;
  try {
    var response = await fetch(request);
    if (response && response.status === 200) {
      var cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    return new Response("离线，资源不可用", { status: 503 });
  }
}
