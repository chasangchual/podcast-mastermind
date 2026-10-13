const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
async function loadEpisode() {
  const id = document.body.dataset.episodeId, target = document.querySelector("#episode-detail");
  const response = await fetch(`/api/v1/episodes/${id}`);
  if (!response.ok) { target.innerHTML = `<p>Episode could not be loaded.</p>`; return; }
  const episode = await response.json();
  target.innerHTML = `<p class="eyebrow">${escapeHtml(episode.transcript_source || episode.processing_status)}</p><h1>${escapeHtml(episode.title)}</h1><p class="lede">${new Date(episode.published_at).toLocaleDateString()}${episode.participants.length ? ` · ${escapeHtml(episode.participants.join(", "))}` : ""}</p><div class="transcript-copy">${escapeHtml(episode.transcript_text || episode.failure_details || "Transcript is not available yet.")}</div>`;
}
loadEpisode();

