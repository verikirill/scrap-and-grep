// Applies the saved theme before first paint, so a dark-mode reader never
// sees a white flash. Kept as a separate file (not inline) so the page can run
// under a Content-Security-Policy without 'unsafe-inline' scripts.
;(function () {
  try {
    var saved = localStorage.getItem('radar-theme')
    var dark = saved ? saved === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches
    if (dark) document.documentElement.classList.add('dark')
  } catch {
    // Storage can be blocked; the light theme is a fine default.
  }
})()
