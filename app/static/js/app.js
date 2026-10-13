const api = async (path, options = {}) => {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Request failed (${response.status})`); }
  return response.json();
};
const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const date = value => new Intl.DateTimeFormat(undefined, { dateStyle:"medium" }).format(new Date(value));

async function load() {
  const [stats, channels, episodes, health] = await Promise.allSettled([api("/api/v1/stats"), api("/api/v1/channels"), api("/api/v1/episodes"), api("/api/v1/health")]);
  if (stats.status === "fulfilled") { document.querySelector("#channel-count").textContent = stats.value.channels; document.querySelector("#episode-count").textContent = stats.value.episodes; }
  if (health.status === "fulfilled") document.querySelector("#system-status").textContent = health.value.status;
  if (channels.status === "fulfilled") document.querySelector("#channels").innerHTML = channels.value.length ? channels.value.map(c => `<div class="list-item"><div><strong>${escapeHtml(c.title)}</strong><span class="meta">${escapeHtml(c.slug)}</span></div><span class="status ${c.active ? "active" : ""}"></span></div>`).join("") : `<p class="muted">No channels yet. Add the first RSS feed.</p>`;
  if (episodes.status === "fulfilled") document.querySelector("#episodes").innerHTML = episodes.value.length ? episodes.value.map(e => `<div class="episode-item"><a href="/episodes/${e.public_id}">${escapeHtml(e.title)}</a><div class="meta">${date(e.published_at)} · ${escapeHtml(e.transcript_source || e.processing_status)}</div></div>`).join("") : `<p class="muted">Episodes appear here after a sync.</p>`;
}

document.querySelector("#add-channel-toggle").addEventListener("click", () => document.querySelector("#channel-form").classList.toggle("hidden"));
document.querySelector("#channel-form").addEventListener("submit", async event => {
  event.preventDefault(); const form = new FormData(event.currentTarget); const payload = Object.fromEntries(form.entries()); if (!payload.website_url) delete payload.website_url;
  try { await api("/api/v1/channels", { method:"POST", body:JSON.stringify(payload) }); event.currentTarget.reset(); event.currentTarget.classList.add("hidden"); await load(); } catch (error) { alert(error.message); }
});
document.querySelector("#sync-button").addEventListener("click", async event => {
  const button = event.currentTarget, notice = document.querySelector("#sync-message"); button.disabled = true; notice.classList.remove("hidden"); notice.textContent = "Syncing feeds and transcripts. Local transcription may take a while…";
  try { const result = await api("/api/v1/sync", { method:"POST", body:JSON.stringify({ years:2, channels:[] }) }); notice.textContent = `Processed ${result.episodes_processed} episodes; ${result.episodes_failed} failed.`; await load(); } catch (error) { notice.textContent = error.message; } finally { button.disabled = false; }
});
document.querySelector("#search-form").addEventListener("submit", async event => {
  event.preventDefault(); const query = document.querySelector("#search-query").value, section = document.querySelector("#search-results-section"), results = document.querySelector("#search-results"); section.classList.remove("hidden"); results.innerHTML = `<p class="muted">Searching…</p>`;
  try { const matches = await api("/api/v1/search", { method:"POST", body:JSON.stringify({query,limit:10}) }); results.innerHTML = matches.length ? matches.map(m => `<article class="result-item"><span class="score">${m.score.toFixed(3)}</span><strong>${escapeHtml(m.episode_title)}</strong><div class="meta">${escapeHtml(m.channel)} · ${date(m.published_at)}</div><p>${escapeHtml(m.text)}</p></article>`).join("") : `<p class="muted">No matching transcript chunks.</p>`; section.scrollIntoView({behavior:"smooth"}); } catch (error) { results.innerHTML = `<p class="muted">${escapeHtml(error.message)}</p>`; }
});
load();

