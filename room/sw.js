self.addEventListener("push", e => {
  let d = {};
  try { d = e.data.json(); } catch (err) {}
  e.waitUntil(self.registration.showNotification(d.title || "Room", { body: d.body || "", tag: "room", renotify: true }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(clients.matchAll({ type: "window" }).then(open => (open.length ? open[0].focus() : clients.openWindow("./"))));
});
