self.addEventListener('install', event => {
  event.waitUntil(
    caches.open('plant-health-cache-v1').then(cache => {
      return cache.addAll([
        '/',
        '/manifest.json',
        '/icon-192.png',
        '/icon-512.png',
        '/service-worker.js',
        // list other assets you want cached
      ])
    })
  )
})

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request)
    })
  )
})
