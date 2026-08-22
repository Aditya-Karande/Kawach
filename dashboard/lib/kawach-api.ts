export type Child = { id: string; name: string; age: number; monitoring_status?: boolean; pairing_code?: string | null }
export type Alert = { id: string; child_id: string; score: number; status: string; created_at: string; ai_explanation?: { what_happened?: string; why_it_matters?: string; recommended_action?: string; severity_label?: string }; score_breakdown?: Array<{ type?: string; risk_label?: string; weight?: number; content?: string; timestamp?: string }> }
let token: string | null = null
export function getToken() { if (typeof window !== 'undefined') token ||= sessionStorage.getItem('kawach_token'); return token }
export function setToken(value: string | null) { token = value; if (typeof window !== 'undefined') value ? sessionStorage.setItem('kawach_token', value) : sessionStorage.removeItem('kawach_token') }
export function apiBase() { return process.env.NEXT_PUBLIC_API_BASE_URL || process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000' }
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> { const response = await fetch(`${apiBase()}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}), ...init?.headers } }); if (response.status === 401) { setToken(null); if (typeof window !== 'undefined') window.location.href = '/?auth=login' }; if (!response.ok) throw new Error('Unable to complete that request'); return response.json() }
export const auth = (kind: 'login' | 'signup', body: object) => apiFetch<{ access_token: string }>(`/api/auth/${kind}`, { method: 'POST', body: JSON.stringify(body) })
// The backend identifies a child with `child_id` and stores monitoring
// status as the string "on" / "off". The rest of this app works with
// `id` (string) and `monitoring_status` (boolean), so every child object
// coming back from the API is normalized here — this is also what fixes
// the "toggling one child toggles all of them" bug: without this mapping
// every child.id was undefined, so the toggle handler's `item.id === child.id`
// check matched every row at once.
function normalizeChild(raw: any): Child {
    return {
        id: raw.id ?? raw.child_id,
        name: raw.name,
        age: raw.age,
        monitoring_status: raw.monitoring_status === true || raw.monitoring_status === 'on',
        pairing_code: raw.pairing_code ?? null,
    }
}
export const getChildren = async () => (await apiFetch<any[]>('/api/children')).map(normalizeChild)
export const getAlerts = (id: string) => apiFetch<Alert[]>(`/api/alerts/${id}`)
export const feedback = (id: string, verdict: string) => apiFetch(`/api/alerts/${id}/feedback`, { method: 'POST', body: JSON.stringify({ parent_verdict: verdict }) })
export const addChild = async (body: object) => normalizeChild(await apiFetch<any>('/api/children', { method: 'POST', body: JSON.stringify(body) }))
// Backend's ToggleRequest.status is `"on" | "off" | null`, not a boolean —
// send the string it actually expects.
export const toggleMonitoring = (child_id: string, status: boolean) => apiFetch('/api/monitoring/toggle', { method: 'POST', body: JSON.stringify({ child_id, status: status ? 'on' : 'off' }) })
export const getGuardians = (id: string) => apiFetch<string[]>(`/api/guardians/${id}`)
export const addGuardian = (body: object) => apiFetch('/api/guardians', { method: 'POST', body: JSON.stringify(body) })
export const demoChildren: Child[] = [{ id: 'maya', name: 'Maya', age: 12, monitoring_status: true }, { id: 'noah', name: 'Noah', age: 9, monitoring_status: false, pairing_code: 'KWC-4821' }]
export const demoAlerts: Alert[] = [{ id: 'a1', child_id: 'maya', score: 87, status: 'new', created_at: new Date(Date.now() - 2700000).toISOString(), ai_explanation: { severity_label: 'severe', what_happened: 'A conversation included language that may indicate a risky interaction.', why_it_matters: 'The pattern is worth a calm check-in with Maya.', recommended_action: 'Ask an open question about who she was talking to and how it made her feel.' }, score_breakdown: [{ type: 'language', risk_label: 'high', weight: 0.7, content: 'Potentially coercive language detected' }] }, { id: 'a2', child_id: 'maya', score: 42, status: 'reviewed', created_at: new Date(Date.now() - 18000000).toISOString(), ai_explanation: { severity_label: 'moderate', what_happened: 'A message contained a mild safety signal.', why_it_matters: 'Context can help determine whether this was ordinary conversation.', recommended_action: 'Keep an eye on the conversation context.' } }]
export const demoGuardians = ['alex@example.com', 'jordan@example.com']
export function relativeTime(value: string) { const minutes = Math.max(1, Math.round((Date.now() - new Date(value).getTime()) / 60000)); return minutes < 60 ? `${minutes} min ago` : minutes < 1440 ? `${Math.round(minutes / 60)} hr ago` : `${Math.round(minutes / 1440)} days ago` }
export function formatDate(value: string) { return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
export function severityTone(label?: string) { return label === 'severe' || label === 'critical' ? 'severe' : label === 'high' ? 'high' : 'moderate' }
export function childStatus(child: Child) { return child.monitoring_status === true }
export function initials(name: string) { return name.split(' ').map(part => part[0]).join('').slice(0, 2).toUpperCase() }
export function clearAuth() { setToken(null) }
export function logout() { clearAuth(); if (typeof window !== 'undefined') window.location.href = '/' }
export function getParentEmail() { return typeof window === 'undefined' ? 'parent@example.com' : sessionStorage.getItem('kawach_email') || 'parent@example.com' }
export async function safeChildren() { try { return await getChildren() } catch { return demoChildren } }
export async function safeAlerts(id: string) { try { return await getAlerts(id) } catch { return demoAlerts.filter(item => item.child_id === id) } }
export async function safeGuardians(id: string) { try { return await getGuardians(id) } catch { return id === 'maya' ? demoGuardians : [] } }
export async function safeAction<T>(action: () => Promise<T>) { try { return await action() } catch { return null } }