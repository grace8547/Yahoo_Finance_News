async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || response.statusText);
  }
  return response.json();
}

async function loadPodcasts() {
  const podcasts = await fetchJson("/podcasts");
  const list = document.querySelector("#podcasts");
  list.innerHTML = "";
  if (podcasts.length === 0) {
    list.innerHTML = `<div class="status-box">No episodes yet. Generate one to test the pipeline.</div>`;
    return;
  }
  podcasts.forEach((podcast) => {
    const row = document.createElement("div");
    row.className = "episode-row";

    const button = document.createElement("button");
    button.className = "episode-button";
    button.innerHTML = `<strong>${podcast.title}</strong><span class="meta">${podcast.date} - ${podcast.status}</span>`;
    button.addEventListener("click", () => renderEpisode(podcast.id));

    const deleteButton = document.createElement("button");
    deleteButton.className = "delete-button";
    deleteButton.type = "button";
    deleteButton.title = "Delete episode";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", async () => {
      await deletePodcast(podcast.id);
    });

    row.appendChild(button);
    row.appendChild(deleteButton);
    list.appendChild(row);
  });
}

async function deletePodcast(id) {
  const confirmed = window.confirm("Delete this episode and its audio files?");
  if (!confirmed) {
    return;
  }
  await fetchJson(`/podcasts/${id}`, { method: "DELETE" });
  await loadPodcasts();
  const episode = document.querySelector("#episode");
  episode.className = "episode-empty";
  episode.textContent = "Episode deleted.";
}

async function renderEpisode(id) {
  const [podcast, sources] = await Promise.all([
    fetchJson(`/podcasts/${id}`),
    fetchJson(`/podcasts/${id}/sources`),
  ]);
  const episode = document.querySelector("#episode");
  episode.className = "episode-panel";
  episode.innerHTML = `
    <h1>${podcast.title}</h1>
    <p>${podcast.date}</p>
    <audio controls src="${podcast.audio_url}"></audio>
    <div class="script">${podcast.script}</div>
    <div class="sources">
      <h2>Source Articles</h2>
      ${sources.map((source) => `<a href="${source.url}" target="_blank" rel="noreferrer">${source.title}</a>`).join("")}
    </div>
  `;
}

document.querySelector("#generate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button");
  const episode = document.querySelector("#episode");
  const tickers = document.querySelector("#tickers").value.split(",").map((ticker) => ticker.trim()).filter(Boolean);
  button.disabled = true;
  button.textContent = "Generating...";
  episode.className = "episode-panel";
  episode.innerHTML = `
    <h1>Generating briefing</h1>
    <p>Fetching news, deduplicating articles, asking Ollama for a script, and creating audio. Local models can take a few minutes.</p>
    <div class="progress-bar"><span></span></div>
  `;
  try {
    const podcasts = await fetchJson("/jobs/daily", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers }),
    });
    await loadPodcasts();
    if (podcasts.length > 0) {
      await renderEpisode(podcasts[0].id);
    }
  } catch (error) {
    episode.innerHTML = `
      <h1>Generation failed</h1>
      <p>${error.message}</p>
    `;
  } finally {
    button.disabled = false;
    button.textContent = "Generate";
  }
});

loadPodcasts().catch((error) => {
  document.querySelector("#podcasts").textContent = error.message;
});
