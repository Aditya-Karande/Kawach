import { EVENT_TYPES, makeEvent } from '../events/event-schema.js';

const providers = [
  { name: 'Google', hosts: ['google.com', 'www.google.com'], param: 'q' },
  { name: 'Bing', hosts: ['bing.com', 'www.bing.com'], param: 'q' },
  { name: 'DuckDuckGo', hosts: ['duckduckgo.com', 'www.duckduckgo.com'], param: 'q' },
  { name: 'Yahoo', hosts: ['search.yahoo.com'], param: 'p' }
];

export function detectSearch(url) {
  try {
    const u = new URL(url);
    const host = u.hostname.toLowerCase();
    const provider = providers.find(p => p.hosts.includes(host));
    if (!provider) return null;
    const query = u.searchParams.get(provider.param);
    if (!query) return null;
    return makeEvent(EVENT_TYPES.SEARCH, {
      searchEngine: provider.name,
      query: query.slice(0, 1000),
      pageUrl: url,
      domain: host
    });
  } catch { return null; }
}
