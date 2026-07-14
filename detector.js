(() => {
  if (window.__pp_armed) return;
  window.__pp_armed = true;
  const RX = /buy\s*now/i;
  const CANDIDATES = 'button, a, input[type="submit"], [role="button"]';
  const find = () => {
    for (const el of document.querySelectorAll(CANDIDATES)) {
      const t = el.innerText || el.value || el.getAttribute('aria-label') || '';
      if (RX.test(t) && !el.disabled && el.offsetParent !== null) return el;
    }
    return null;
  };
  const fire = (el) => {
    if (window.__pp_found) return;
    window.__pp_found = Date.now();
    try { sessionStorage.setItem('__pp_found', String(window.__pp_found)); } catch (e) {}
    el.click();
  };
  const now = find();
  if (now) return fire(now);
  new MutationObserver(() => {
    const el = find();
    if (el) fire(el);
  }).observe(document.documentElement, {
    subtree: true, childList: true,
    attributes: true, attributeFilter: ['disabled', 'class', 'style', 'hidden'],
  });
})();
