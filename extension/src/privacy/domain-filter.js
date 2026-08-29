const SENSITIVE_HOST_HINTS = [
  'bank', 'paypal', 'stripe', 'wallet', 'password', 'pass', 'auth', 'login',
  'medical', 'health', 'clinic', 'hospital', 'insurance'
];

export function hostnameFromUrl(url) {
  try { return new URL(url).hostname.toLowerCase(); } catch { return ''; }
}

export function domainMatches(hostname, excluded) {
  const h = hostnameFromUrl(hostname) || hostname;
  const e = excluded.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
  return !!e && (h === e || h.endsWith(`.${e}`));
}

export function isExcluded(url, settings) {
  const host = hostnameFromUrl(url);
  return settings.excludedDomains.some(d => domainMatches(host, d));
}

export function looksSensitive(url) {
  const host = hostnameFromUrl(url);
  return SENSITIVE_HOST_HINTS.some(h => host.includes(h));
}

export function shouldIgnore(url, settings) {
  if (!url || !/^https?:/i.test(url)) return true;
  if (isExcluded(url, settings)) return true;
  if (settings.protectSensitiveSites && looksSensitive(url)) return true;
  return false;
}
