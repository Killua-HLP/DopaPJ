const GUEST_FAVORITES_KEY = "anime-hub-watchlist";
const FEATURED_ANIME_COUNT = 10;
const FEATURED_ROTATION_MS = 6000;
const MOOD_OPTIONS = {
    cozy: { genre: "Slice of Life", reason: "A gentle, easygoing story for a cozy mood." },
    hype: { genre: "Action", reason: "High energy and big moments for an exciting watch." },
    "mind-bending": { genre: "Psychological", reason: "A twisty, thought-provoking pick to keep you guessing." },
    heartfelt: { genre: "Drama", reason: "An emotional story with room to make an impression." },
    fantasy: { genre: "Fantasy", reason: "A chance to step into a different world." },
};
const api = window.AnimeHubApi;
const animeContainer = document.getElementById("anime-container");
const catalogState = document.getElementById("catalog-state");
const searchInput = document.getElementById("anime-input");
const sortSelect = document.getElementById("sort-select");
const genreFilters = document.getElementById("genre-filters");
const resultsCount = document.getElementById("results-count");
const collectionSortControl = document.querySelector(".sort-control");
const watchlistToggle = document.getElementById("watchlist-toggle");
const watchlistCount = document.getElementById("watchlist-count");
const addAnimeButton = document.getElementById("add-anime-button");
const animeDialog = document.getElementById("anime-dialog");
const animeForm = document.getElementById("anime-form");
const animeFormFeedback = document.getElementById("anime-form-feedback");
const catalogSearchForm = document.getElementById("catalog-search-form");
const catalogSearchInput = document.getElementById("catalog-search-input");
const catalogSearchFeedback = document.getElementById("catalog-search-feedback");
const catalogSearchResults = document.getElementById("catalog-search-results");
const catalogImportAllButton = document.getElementById("catalog-import-all");
const discoveryFilters = document.getElementById("discovery-filters");
const semanticSearchForm = document.getElementById("semantic-search-form");
const semanticSearchInput = document.getElementById("semantic-search-input");
const semanticSearchFeedback = document.getElementById("semantic-search-feedback");
const catalogPagination = document.getElementById("catalog-pagination");
const catalogPageLabel = document.getElementById("catalog-page-label");
const discoveryControls = {
    year: document.getElementById("filter-year"),
    season: document.getElementById("filter-season"),
    format: document.getElementById("filter-format"),
    status: document.getElementById("filter-status"),
    genre: document.getElementById("filter-genre"),
    rating: document.getElementById("filter-rating"),
    sort: document.getElementById("filter-sort"),
};

let animeList = [];
let catalogSearchResultsData = [];
let favoriteIds = [];
let selectedGenre = "All";
let showingWatchlist = false;
let catalogMode = "collection";
let externalCatalogPage = 1;
let externalCatalogHasNext = false;
let externalSearchTimer;
let externalCatalogData = [];
let featuredAnimeList = [];
let featuredIndex = 0;
let featuredRotationTimer;
let featuredTransitionTimer;
let semanticSearchActive = false;

function leaveSemanticSearch() {
    semanticSearchActive = false;
    semanticSearchFeedback.textContent = "";
}

function readGuestFavorites() {
    try {
        const saved = JSON.parse(localStorage.getItem(GUEST_FAVORITES_KEY) || "[]");
        return Array.isArray(saved) ? saved.filter(Number.isInteger) : [];
    } catch (error) {
        console.error("Could not read the guest watchlist:", error);
        return [];
    }
}
    semanticSearchForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const query = semanticSearchInput.value.trim();
        if (query.length < 3) return;
        const button = semanticSearchForm.querySelector('button[type="submit"]');
        button.disabled = true;
        semanticSearchFeedback.textContent = "Searching by synopsis and genre meaning...";
        try {
            const response = await api.request("/catalog/semantic-search", {
                method: "POST",
                body: JSON.stringify({ query, limit: 12 }),
            });
            semanticSearchActive = true;
            catalogMode = "collection";
            animeContainer.replaceChildren(...response.results.map(createAnimeCard));
            resultsCount.textContent = `${response.results.length} semantic matches`;
            semanticSearchFeedback.textContent = response.results.length
                ? `Closest matches for “${query}”.`
                : "No close matches yet. Try describing a different mood, genre, or story detail.";
            catalogPagination.hidden = true;
            clearState();
        } catch (error) {
            console.error("Semantic anime search failed:", error);
            semanticSearchFeedback.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    });

    semanticSearchInput.addEventListener("input", () => {
        if (!semanticSearchActive) return;
        semanticSearchActive = false;
        semanticSearchFeedback.textContent = "";
        renderGenreFilters();
        renderCatalog();
    });


function saveGuestFavorites() {
    try {
        localStorage.setItem(GUEST_FAVORITES_KEY, JSON.stringify(favoriteIds));
        return true;
    } catch (error) {
        console.error("Could not save the guest watchlist:", error);
        return false;
    }
}

function getRating(anime) {
    if (anime.rating === null || anime.rating === undefined || anime.rating === "") return null;
    const rating = Number(anime.rating);
    return Number.isFinite(rating) ? rating : null;
}

function showState(title, message, actionText, action) {
    catalogState.replaceChildren();
    const heading = document.createElement("strong");
    heading.textContent = title;
    const detail = document.createElement("span");
    detail.textContent = message;
    catalogState.append(heading, detail);
    if (actionText && action) {
        const button = document.createElement("button");
        button.className = "state-action";
        button.type = "button";
        button.textContent = actionText;
        button.addEventListener("click", action);
        catalogState.append(button);
    }
    catalogState.hidden = false;
}

function clearState() {
    catalogState.hidden = true;
    catalogState.replaceChildren();
}

function imageUrl(value) {
    if (!value) return "";
    const source = String(value).trim();
    if (!source || source.toLowerCase() === "string") return "";
    try {
        const isAbsolute = /^https?:\/\//i.test(source);
        const path = source.startsWith("/static/")
            ? source
            : source.startsWith("/")
                ? `/static${source}`
                : `/static/${source}`;
        const url = new URL(isAbsolute ? source : path, window.location.origin);
        return ["http:", "https:"].includes(url.protocol) ? url.href : "";
    } catch {
        return "";
    }
}

function createPosterPlaceholder(title, genre, className) {
    const placeholder = document.createElement("div");
    placeholder.className = `${className} poster-placeholder`;
    const ornament = document.createElement("span");
    ornament.className = "placeholder-ornament";
    ornament.setAttribute("aria-hidden", "true");
    ornament.textContent = "✳";
    const caption = document.createElement("span");
    caption.className = "placeholder-caption";
    caption.textContent = genre || "ANIME HUB COLLECTION";
    const heading = document.createElement("strong");
    heading.className = "placeholder-title";
    heading.textContent = title;
    placeholder.append(ornament, caption, heading);
    return placeholder;
}

function getGenres() {
    return [...new Set(animeList.flatMap((anime) => (
        (anime.genre || "").split(",").map((genre) => genre.trim()).filter(Boolean)
    )))].sort((a, b) => a.localeCompare(b));
}

function renderGenreFilters() {
    genreFilters.replaceChildren();
    ["All", ...getGenres()].forEach((genre) => {
        const button = document.createElement("button");
        button.className = "genre-chip";
        button.type = "button";
        button.textContent = genre;
        button.setAttribute("aria-pressed", String(selectedGenre === genre));
        button.addEventListener("click", () => {
            selectedGenre = genre;
            leaveSemanticSearch();
            renderGenreFilters();
            renderCatalog();
        });
        genreFilters.append(button);
    });
}

function renderHero() {
    const featured = featuredAnimeList[featuredIndex]
        || [...animeList].sort((a, b) => (getRating(b) ?? 0) - (getRating(a) ?? 0))[0];
    if (!featured) return;

    const poster = imageUrl(featured.cover_image);
    if (poster) {
        const safePoster = poster.replaceAll('"', "%22");
        document.getElementById("hero-art").style.backgroundImage = `url("${safePoster}")`;
        document.getElementById("hero-backdrop").style.backgroundImage = `url("${safePoster}")`;
        document.getElementById("hero-art").replaceChildren();
    } else {
        const art = document.getElementById("hero-art");
        art.style.backgroundImage = "";
        art.replaceChildren(createPosterPlaceholder(featured.title, featured.genre, "hero-poster-placeholder"));
    }

    const title = document.getElementById("hero-title");
    title.replaceChildren(document.createTextNode(`${featured.title} — `));
    const highlight = document.createElement("span");
    highlight.textContent = "now streaming.";
    title.append(document.createElement("br"), highlight);
    const description = document.querySelector(".hero-copy");
    description.textContent = featured.description || "Discover a new world in this fan-favorite series.";
    description.classList.remove("is-expanded");
    const readMore = document.getElementById("hero-read-more");
    const hasLongDescription = description.textContent.length > 180;
    readMore.hidden = !hasLongDescription;
    readMore.textContent = "Read more";
    readMore.setAttribute("aria-expanded", "false");

    const featuredLink = document.getElementById("hero-featured");
    if (featured.source_url) {
        featuredLink.href = featured.source_url;
        featuredLink.target = "_blank";
        featuredLink.rel = "noopener noreferrer";
        featuredLink.lastChild.textContent = " View on AniList ↗";
    } else {
        const featuredId = Number(featured.id);
        if (!Number.isSafeInteger(featuredId) || featuredId < 1) {
            console.error("Featured anime has an invalid catalog ID:", featured.id);
            featuredLink.hidden = true;
            return;
        }
        featuredLink.href = `/anime-detail.html?id=${featuredId}`;
        featuredLink.target = "_self";
        featuredLink.removeAttribute("rel");
        featuredLink.lastChild.textContent = " Featured title";
    }
    featuredLink.hidden = false;

    document.querySelectorAll(".hero-pagination button").forEach((button, index) => {
        button.setAttribute("aria-pressed", String(index === featuredIndex));
    });

    const ratingValue = getRating(featured);
    const rating = document.getElementById("hero-rating");
    rating.replaceChildren();
    if (ratingValue !== null) {
        const star = document.createElement("span");
        star.textContent = "★";
        star.style.color = "var(--gold)";
        const score = document.createElement("strong");
        score.textContent = ratingValue.toFixed(1);
        const divider = document.createElement("span");
        divider.textContent = "·";
        const genre = document.createElement("span");
        genre.textContent = featured.genre || "Anime";
        rating.append(star, score, divider, genre);
        rating.hidden = false;
    }
}

document.getElementById("hero-read-more").addEventListener("click", (event) => {
    const button = event.currentTarget;
    const expanded = button.getAttribute("aria-expanded") !== "true";
    document.querySelector(".hero-copy").classList.toggle("is-expanded", expanded);
    button.setAttribute("aria-expanded", String(expanded));
    button.textContent = expanded ? "Read less" : "Read more";
});

document.getElementById("mood-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = form.querySelector('[type="submit"]');
    const feedback = document.getElementById("mood-feedback");
    const resultsContainer = document.getElementById("mood-results");
    const mood = MOOD_OPTIONS[document.getElementById("mood-choice").value];
    const availableMinutes = Number(document.getElementById("mood-time").value);
    const requestedFormat = document.getElementById("mood-format").value;
    const picks = [];
    const seenTitles = new Set();
    submit.disabled = true;
    resultsContainer.replaceChildren();
    feedback.textContent = "Finding popular picks for your mood...";

    try {
        for (let page = 1; page <= 4 && picks.length < 3; page += 1) {
            const params = new URLSearchParams({
                page: String(page),
                genre: mood.genre,
                sort: "POPULARITY_DESC",
                min_rating: "6",
            });
            if (requestedFormat !== "ANY") params.set("format", requestedFormat);
            const response = await api.request(`/catalog/browse?${params}`);
            if (!response || !Array.isArray(response.results)) {
                throw new Error("The catalog returned unexpected mood-pick results.");
            }
            for (const anime of response.results) {
                const normalizedTitle = anime.title.toLocaleLowerCase();
                if (seenTitles.has(normalizedTitle)) continue;
                seenTitles.add(normalizedTitle);
                if (!anime.duration || !["MOVIE", "TV", "TV_SHORT", "ONA", "OVA"].includes(anime.format)) continue;

                const isMovie = anime.format === "MOVIE";
                if (isMovie && anime.duration > availableMinutes) continue;
                if (!isMovie && anime.duration > availableMinutes) continue;
                const episodesFit = Math.max(1, Math.floor(availableMinutes / anime.duration));
                const episodeCount = anime.episode
                    ? Math.min(episodesFit, anime.episode)
                    : episodesFit;
                picks.push({
                    anime,
                    reason: isMovie
                        ? `${mood.reason} Its ${anime.duration}-minute runtime fits your time.`
                        : `${mood.reason} You could watch up to ${episodeCount} episode${episodeCount === 1 ? "" : "s"} in your time.`,
                });
                if (picks.length === 3) break;
            }
            if (!response.has_next) break;
        }

        if (!picks.length) {
            feedback.textContent = "No popular matches fit that time and format. Try more time or another format.";
            return;
        }

        const cards = picks.map(({ anime, reason }) => {
            const card = document.createElement("article");
            card.className = "mood-pick";
            const cover = imageUrl(anime.cover_image);
            if (cover) {
                const image = document.createElement("img");
                image.src = cover;
                image.alt = `${anime.title} cover`;
                image.loading = "lazy";
                card.append(image);
            }
            const details = document.createElement("div");
            details.className = "mood-pick-info";
            const title = document.createElement("h3");
            title.textContent = anime.title;
            const metadata = document.createElement("p");
            metadata.className = "mood-pick-meta";
            metadata.textContent = [
                anime.rating ? `★ ${Number(anime.rating).toFixed(1)}` : null,
                anime.format === "MOVIE" ? `${anime.duration} min movie` : `${anime.duration} min / episode`,
            ].filter(Boolean).join(" · ");
            const explanation = document.createElement("p");
            explanation.className = "mood-pick-reason";
            explanation.textContent = reason;
            const link = document.createElement("a");
            link.className = "detail-link";
            link.href = anime.source_url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = "View on AniList ↗";
            details.append(title, metadata, explanation, link);
            card.append(details);
            return card;
        });
        resultsContainer.replaceChildren(...cards);
        feedback.textContent = `Here are ${picks.length} popular ${mood.genre.toLocaleLowerCase()} picks for you.`;
    } catch (error) {
        console.error("Could not find mood-based anime picks:", error);
        feedback.textContent = `Couldn't find picks right now. ${error.message}`;
    } finally {
        submit.disabled = false;
    }
});

async function loadFeaturedAnime() {
    let featuredTitles = [];
    try {
        const response = await api.request("/catalog/browse?page=1&sort=POPULARITY_DESC");
        if (!response || !Array.isArray(response.results)) {
            throw new Error("The catalog returned an unexpected featured list.");
        }
        featuredTitles = response.results
            .filter((anime) => anime.title && anime.source_url)
            .slice(0, FEATURED_ANIME_COUNT);
        if (!featuredTitles.length) {
            throw new Error("The catalog returned no titles for the featured list.");
        }
    } catch (error) {
        console.warn("Could not load online featured anime; using the local collection instead:", error);
        featuredTitles = [...animeList]
            .filter((anime) => anime.title && Number.isSafeInteger(Number(anime.id)) && Number(anime.id) > 0)
            .sort((a, b) => (getRating(b) ?? 0) - (getRating(a) ?? 0))
            .slice(0, FEATURED_ANIME_COUNT)
            .map((anime) => ({ ...anime, source_url: null }));
    }
    if (!featuredTitles.length) {
        throw new Error("The catalog returned no titles for the featured list.");
    }
    featuredAnimeList = featuredTitles;
    featuredIndex = 0;
    const indicators = document.querySelector(".hero-pagination");
    indicators.replaceChildren(...featuredAnimeList.map((anime, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.setAttribute("aria-label", `Show featured anime ${index + 1}: ${anime.title}`);
        button.setAttribute("aria-pressed", String(index === featuredIndex));
        button.addEventListener("click", () => showFeaturedAnime(index));
        return button;
    }));
    renderHero();
    window.clearInterval(featuredRotationTimer);
    featuredRotationTimer = window.setInterval(() => {
        const hero = document.querySelector(".hero");
        const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (document.hidden || hero.matches(":hover") || hero.contains(document.activeElement) || prefersReducedMotion) {
            return;
        }
        showFeaturedAnime((featuredIndex + 1) % featuredAnimeList.length);
    }, FEATURED_ROTATION_MS);
}

function showFeaturedAnime(index) {
    if (!featuredAnimeList.length) return;
    featuredIndex = index;
    const hero = document.querySelector(".hero");
    window.clearTimeout(featuredTransitionTimer);
    hero.classList.add("is-changing");
    featuredTransitionTimer = window.setTimeout(() => {
        renderHero();
        hero.classList.remove("is-changing");
    }, 180);
}

function createAnimeCard(anime) {
    const card = document.createElement("article");
    card.className = "anime-card";
    const posterWrap = document.createElement("div");
    posterWrap.className = "poster-wrap";
    const posterLink = document.createElement("a");
    posterLink.className = "poster-link";
    posterLink.href = `/anime-detail.html?id=${encodeURIComponent(anime.id)}`;
    posterLink.setAttribute("aria-label", `View details for ${anime.title}`);
    const posterClass = "anime-poster";
    const src = imageUrl(anime.cover_image);
    if (src) {
        const poster = document.createElement("img");
        poster.className = posterClass;
        poster.alt = `${anime.title} cover`;
        poster.loading = "lazy";
        poster.decoding = "async";
        poster.src = src;
        poster.addEventListener("error", () => {
            poster.replaceWith(createPosterPlaceholder(anime.title, anime.genre, posterClass));
        }, { once: true });
        posterLink.append(poster);
    } else {
        posterLink.append(createPosterPlaceholder(anime.title, anime.genre, posterClass));
    }
    posterWrap.append(posterLink);

    const ratingValue = getRating(anime);
    if (ratingValue !== null) {
        const rating = document.createElement("span");
        rating.className = "rating-badge";
        rating.textContent = `★ ${ratingValue.toFixed(1)}`;
        posterWrap.append(rating);
    }

    const favorite = document.createElement("button");
    favorite.className = "favorite-button";
    favorite.type = "button";
    favorite.setAttribute("aria-label", favoriteIds.includes(anime.id) ? `Remove ${anime.title} from watchlist` : `Add ${anime.title} to watchlist`);
    favorite.setAttribute("aria-pressed", String(favoriteIds.includes(anime.id)));
    favorite.textContent = favoriteIds.includes(anime.id) ? "♥" : "♡";
    favorite.addEventListener("click", () => toggleFavorite(anime.id));
    posterWrap.append(favorite);

    const info = document.createElement("div");
    info.className = "card-info";
    const title = document.createElement("h3");
    title.className = "card-title";
    title.textContent = anime.title;
    title.title = anime.title;
    const meta = document.createElement("div");
    meta.className = "card-meta";
    const genre = document.createElement("span");
    genre.className = "card-genre";
    genre.textContent = anime.genre || "Anime";
    const year = document.createElement("span");
    year.textContent = anime.released_date ? String(anime.released_date).slice(0, 4) : "";
    meta.append(genre, year);
    if (typeof anime.similarity === "number") {
        const match = document.createElement("span");
        match.className = "semantic-match-score";
        match.textContent = `${Math.round(anime.similarity * 100)}% match`;
        meta.append(match);
    }
    const link = document.createElement("a");
    link.className = "detail-link";
    link.href = `/anime-detail.html?id=${encodeURIComponent(anime.id)}`;
    link.textContent = "View details";
    link.setAttribute("aria-label", `View details for ${anime.title}`);
    info.append(title, meta, link);
    card.append(posterWrap, info);
    return card;
}

function renderCatalog() {
    if (semanticSearchActive) return;
    if (catalogMode !== "collection") return;
    const keyword = searchInput.value.trim().toLocaleLowerCase();
    let result = animeList.filter((anime) => {
        const matchesSearch = [anime.title, anime.genre, anime.studio, anime.description]
            .some((value) => String(value || "").toLocaleLowerCase().includes(keyword));
        const matchesGenre = selectedGenre === "All" || (anime.genre || "")
            .split(",").some((genre) => genre.trim() === selectedGenre);
        return matchesSearch && matchesGenre && (!showingWatchlist || favoriteIds.includes(anime.id));
    });

    if (sortSelect.value === "name") result.sort((a, b) => a.title.localeCompare(b.title));
    else if (sortSelect.value === "ratingLow") result.sort((a, b) => (getRating(a) ?? 0) - (getRating(b) ?? 0));
    else if (sortSelect.value === "newest") result.sort((a, b) => String(b.released_date || "").localeCompare(String(a.released_date || "")));
    else result.sort((a, b) => (getRating(b) ?? 0) - (getRating(a) ?? 0));

    animeContainer.replaceChildren(...result.map(createAnimeCard));
    resultsCount.textContent = `${result.length} ${result.length === 1 ? "title" : "titles"}`;
    if (!result.length) {
        const emptyWatchlist = showingWatchlist && !keyword && selectedGenre === "All";
        const noTitles = animeList.length === 0 && !keyword && selectedGenre === "All";
        showState(
            emptyWatchlist ? "Your watchlist is waiting" : noTitles ? "The collection is just getting started" : "No anime found",
            emptyWatchlist ? "Tap the heart on any title to save it here."
                : noTitles ? "Add your first anime and share it with the community."
                    : "Try another title or genre, or clear your filters.",
            noTitles ? "" : emptyWatchlist ? "" : "Clear filters",
            noTitles || emptyWatchlist ? null : () => {
                searchInput.value = "";
                selectedGenre = "All";
                renderGenreFilters();
                renderCatalog();
            },
        );
    } else {
        clearState();
    }
}

function createExternalAnimeCard(anime) {
    const card = document.createElement("article");
    card.className = "anime-card";
    const posterWrap = document.createElement("div");
    posterWrap.className = "poster-wrap";
    const posterLink = document.createElement("a");
    posterLink.className = "poster-link";
    posterLink.href = anime.source_url;
    posterLink.target = "_blank";
    posterLink.rel = "noopener noreferrer";
    posterLink.setAttribute("aria-label", `View ${anime.title} on AniList`);
    const cover = imageUrl(anime.cover_image);
    if (cover) {
        const image = document.createElement("img");
        image.className = "anime-poster";
        image.alt = `${anime.title} cover`;
        image.loading = "lazy";
        image.src = cover;
        image.addEventListener("error", () => image.replaceWith(
            createPosterPlaceholder(anime.title, anime.genre, "anime-poster"),
        ), { once: true });
        posterLink.append(image);
    } else {
        posterLink.append(createPosterPlaceholder(anime.title, anime.genre, "anime-poster"));
    }
    posterWrap.append(posterLink);
    if (getRating(anime) !== null) {
        const rating = document.createElement("span");
        rating.className = "rating-badge";
        rating.textContent = `★ ${getRating(anime).toFixed(1)}`;
        posterWrap.append(rating);
    }

    const info = document.createElement("div");
    info.className = "card-info";
    const title = document.createElement("h3");
    title.className = "card-title";
    title.textContent = anime.title;
    const meta = document.createElement("div");
    meta.className = "card-meta";
    const genre = document.createElement("span");
    genre.className = "card-genre";
    genre.textContent = anime.genre || "Anime";
    const year = document.createElement("span");
    year.textContent = anime.released_date ? anime.released_date.slice(0, 4) : "";
    meta.append(genre, year);
    const sourceLink = document.createElement("a");
    sourceLink.className = "detail-link";
    sourceLink.href = anime.source_url;
    sourceLink.target = "_blank";
    sourceLink.rel = "noreferrer";
    sourceLink.textContent = "View on AniList ↗";
    const addButton = document.createElement("button");
    addButton.className = "catalog-add-button";
    addButton.type = "button";
    const alreadyAdded = animeList.some((saved) => (
        saved.title.toLocaleLowerCase() === anime.title.toLocaleLowerCase()
    ));
    addButton.textContent = alreadyAdded ? "Already in collection" : "＋ Add to collection";
    addButton.disabled = alreadyAdded;
    addButton.addEventListener("click", async () => {
        if (!api.getToken()) {
            window.location.href = "/login.html";
            return;
        }
        addButton.disabled = true;
        addButton.textContent = "Adding...";
        try {
            await saveCatalogAnime(anime);
            addButton.textContent = "Added";
            renderGenreFilters();
        } catch (error) {
            console.error("Could not add catalog anime:", error);
            addButton.textContent = error.status === 409 ? "Already in collection" : "Try again";
            addButton.disabled = error.status === 409;
        }
    });
    const explanationButton = document.createElement("button");
    explanationButton.className = "detail-link explanation-button";
    explanationButton.type = "button";
    explanationButton.textContent = "Why you might like it";
    const explanation = document.createElement("p");
    explanation.className = "recommendation-explanation";
    explanation.setAttribute("aria-live", "polite");
    explanationButton.addEventListener("click", async () => {
        explanationButton.disabled = true;
        explanation.textContent = "Generating a short explanation...";
        try {
            const result = await api.request("/catalog/recommendation-explanation", {
                method: "POST",
                body: JSON.stringify({
                    title: anime.title,
                    synopsis: anime.description || "No synopsis is available.",
                    genres: (anime.genre || "").split(",").map((value) => value.trim()).filter(Boolean),
                }),
            });
            explanation.textContent = result.explanation;
        } catch (error) {
            console.error("Could not generate recommendation explanation:", error);
            explanation.textContent = error.message;
        } finally {
            explanationButton.disabled = false;
        }
    });
    info.append(title, meta, sourceLink, explanationButton, explanation, addButton);
    card.append(posterWrap, info);
    return card;
}

function populateDiscoveryFilters() {
    const currentYear = new Date().getFullYear();
    for (let year = currentYear + 1; year >= 1940; year -= 1) {
        const option = document.createElement("option");
        option.value = String(year);
        option.textContent = String(year);
        discoveryControls.year.append(option);
    }
    [
        "Action", "Adventure", "Comedy", "Drama", "Fantasy", "Horror", "Mystery",
        "Psychological", "Romance", "Sci-Fi", "Slice of Life", "Sports", "Supernatural",
        "Thriller",
    ].forEach((genre) => {
        const option = document.createElement("option");
        option.value = genre;
        option.textContent = genre;
        discoveryControls.genre.append(option);
    });
}

function discoveryQuery(page) {
    const params = new URLSearchParams({ page: String(page) });
    const query = searchInput.value.trim();
    if (query) params.set("q", query);
    Object.entries(discoveryControls).forEach(([key, control]) => {
        if (control.value) params.set(key === "rating" ? "min_rating" : key, control.value);
    });
    return params;
}

async function loadExternalCatalog(page = 1) {
    externalCatalogPage = page;
    const grid = animeContainer;
    grid.replaceChildren();
    showState("Searching the anime universe...", "Loading matches from AniList.");
    catalogPagination.hidden = true;
    catalogPageLabel.textContent = "";
    resultsCount.textContent = "";
    let path = catalogMode === "recommendations"
        ? `/catalog/recommendations?page=${page}`
        : `/catalog/browse?${discoveryQuery(page)}`;

    try {
        const response = await api.request(path);
        if (!response || !Array.isArray(response.results)) {
            throw new Error("The catalog returned an unexpected response.");
        }
        externalCatalogData = response.results;
        externalCatalogHasNext = response.has_next;
        if (externalCatalogData.length) {
            grid.replaceChildren(...externalCatalogData.map(createExternalAnimeCard));
            clearState();
            resultsCount.textContent = `${response.total.toLocaleString()} results`;
        } else {
            resultsCount.textContent = "0 results";
            const message = catalogMode === "recommendations"
                ? "Save a few favorites or mark shows completed to get personalized picks."
                : "No titles match these filters. Try broadening your search.";
            showState("No titles to show yet", message);
        }
        catalogPageLabel.textContent = `Page ${response.page} · ${response.total.toLocaleString()} titles`;
        document.getElementById("catalog-prev").disabled = response.page <= 1;
        document.getElementById("catalog-next").disabled = !response.has_next;
        catalogPagination.hidden = false;
    } catch (error) {
        console.error("Could not browse the anime catalog:", error);
        resultsCount.textContent = "";
        showState("Couldn't load catalog results", error.message, "Try again", () => loadExternalCatalog(page));
    }
}

function setCatalogMode(mode) {
    leaveSemanticSearch();
    catalogMode = mode;
    showingWatchlist = false;
    updateWatchlistButton();
    if (mode === "trending") {
        discoveryControls.sort.value = "TRENDING_DESC";
    } else if (mode === "seasonal") {
        const now = new Date();
        discoveryControls.year.value = String(now.getFullYear());
        discoveryControls.season.value = ["WINTER", "WINTER", "SPRING", "SPRING", "SPRING", "SUMMER", "SUMMER", "SUMMER", "FALL", "FALL", "FALL", "WINTER"][now.getMonth()];
        discoveryControls.status.value = "RELEASING";
        discoveryControls.sort.value = "POPULARITY_DESC";
    }
    document.querySelectorAll("[data-catalog-mode]").forEach((button) => {
        const active = button.dataset.catalogMode === mode;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
    });
    const external = mode !== "collection";
    discoveryFilters.hidden = !["browse", "trending", "seasonal"].includes(mode);
    genreFilters.hidden = external;
    collectionSortControl.hidden = external;
    searchInput.placeholder = external ? "Search the anime universe..." : "Search your collection...";
    catalogPagination.hidden = true;
    animeContainer.replaceChildren();
    if (mode === "collection") {
        renderGenreFilters();
        renderCatalog();
    } else if (mode === "recommendations" && !api.getToken()) {
        resultsCount.textContent = "";
        showState(
            "Your anime, your next favorite",
            "Sign in and save favorites or complete shows to get personal recommendations.",
            "Sign in",
            () => window.location.assign("/login.html"),
        );
    } else {
        loadExternalCatalog(1);
    }
}

function updateWatchlistButton() {
    watchlistCount.textContent = String(favoriteIds.length);
    watchlistToggle.setAttribute("aria-pressed", String(showingWatchlist));
    watchlistToggle.querySelector("span:nth-child(2)").textContent = showingWatchlist ? "All anime" : "My watchlist";
}

async function toggleFavorite(animeId) {
    const wasSaved = favoriteIds.includes(animeId);
    const token = api.getToken();
    try {
        if (token) {
            await api.request(`/users/me/favorites/${animeId}`, { method: wasSaved ? "DELETE" : "POST" });
        } else {
            favoriteIds = wasSaved
                ? favoriteIds.filter((id) => id !== animeId)
                : [...favoriteIds, animeId];
            if (!saveGuestFavorites()) {
                favoriteIds = wasSaved ? [...favoriteIds, animeId] : favoriteIds.filter((id) => id !== animeId);
                throw new Error("Your browser couldn't save the watchlist. Check its storage settings.");
            }
        }
        if (token) {
            favoriteIds = wasSaved
                ? favoriteIds.filter((id) => id !== animeId)
                : [...favoriteIds, animeId];
        }
        updateWatchlistButton();
        renderCatalog();
    } catch (error) {
        console.error("Could not update the watchlist:", error);
        showState("Couldn't update your watchlist", error.message);
    }
}

async function loadAnime() {
    showState("Loading your next favorite...", "Fetching the Anime Hub collection.");
    try {
        const data = await api.request("/anime");
        if (!Array.isArray(data)) throw new Error("The anime service returned an unexpected response.");
        animeList = data;
        try {
            await loadFeaturedAnime();
        } catch (error) {
            console.error("Could not load the featured anime:", error);
        }

        if (api.getToken()) {
            try {
                const saved = await api.request("/users/me/favorites");
                favoriteIds = saved.map((anime) => anime.id);
            } catch (error) {
                if (error.status === 401) api.clearToken();
                else throw error;
                favoriteIds = readGuestFavorites();
            }
        } else {
            favoriteIds = readGuestFavorites();
        }

        favoriteIds = favoriteIds.filter((id) => animeList.some((anime) => anime.id === id));
        updateWatchlistButton();
        renderHero();
        renderGenreFilters();
        renderCatalog();
    } catch (error) {
        console.error("Failed to load the anime collection:", error);
        showState("We couldn't load the collection", error.message || "Check your connection and try again.", "Try again", loadAnime);
    }
}

function showAnimeForm() {
    if (!api.getToken()) {
        window.location.href = "/login.html";
        return;
    }
    animeForm.reset();
    animeFormFeedback.textContent = "";
    catalogSearchForm.reset();
    catalogSearchFeedback.textContent = "";
    catalogSearchResults.replaceChildren();
    catalogImportAllButton.hidden = true;
    animeDialog.showModal();
}

async function saveCatalogAnime(anime) {
    const created = await api.request("/anime", {
        method: "POST",
        body: JSON.stringify(anime),
    });
    animeList.push(created);
    return created;
}

function renderCatalogSearchResults(results) {
    catalogSearchResultsData = results;
    catalogSearchResults.replaceChildren();
    catalogImportAllButton.hidden = results.length < 2;
    if (!results.length) {
        catalogSearchFeedback.textContent = "No matches found. Try another title.";
        return;
    }

    results.forEach((anime) => {
        const item = document.createElement("article");
        item.className = "catalog-result";
        if (anime.cover_image) {
            const image = document.createElement("img");
            image.alt = "";
            image.loading = "lazy";
            image.src = anime.cover_image;
            image.addEventListener("error", () => image.remove(), { once: true });
            item.append(image);
        }

        const details = document.createElement("div");
        details.className = "catalog-result-details";
        const title = document.createElement("strong");
        title.textContent = anime.title;
        const metadata = document.createElement("span");
        const rating = anime.rating === null || anime.rating === undefined || anime.rating === ""
            ? null
            : Number(anime.rating);
        const metadataParts = [anime.genre, rating !== null && Number.isFinite(rating) ? `★ ${rating.toFixed(1)}/10` : null]
            .filter(Boolean);
        metadata.textContent = metadataParts.join(" · ");
        const source = document.createElement("a");
        source.href = anime.source_url;
        source.target = "_blank";
        source.rel = "noreferrer";
        source.textContent = "View on AniList";
        details.append(title, metadata, source);
        const extra = document.createElement("span");
        extra.className = "catalog-result-extra";
        extra.textContent = [anime.episode ? `${anime.episode} episodes` : null, anime.studio]
            .filter(Boolean).join(" · ");
        if (extra.textContent) details.append(extra);

        const addButton = document.createElement("button");
        addButton.className = "button button-primary catalog-add-button";
        addButton.type = "button";
        const alreadyAdded = animeList.some((saved) => saved.title.toLocaleLowerCase() === anime.title.toLocaleLowerCase());
        addButton.textContent = alreadyAdded ? "Already added" : "＋ Add";
        addButton.disabled = alreadyAdded;
        addButton.addEventListener("click", async () => {
            addButton.disabled = true;
            addButton.textContent = "Adding...";
            try {
                const created = await saveCatalogAnime(anime);
                renderHero();
                renderGenreFilters();
                renderCatalog();
                catalogSearchFeedback.textContent = `${created.title} was added. You can import another title.`;
                addButton.textContent = "Added";
            } catch (error) {
                console.error("Could not import anime:", error);
                catalogSearchFeedback.textContent = error.message;
                addButton.disabled = false;
                addButton.textContent = "＋ Add";
            }
        });

        item.append(details, addButton);
        catalogSearchResults.append(item);
    });
    catalogSearchFeedback.textContent = `${results.length} results from AniList`;
}

catalogImportAllButton.addEventListener("click", async () => {
    catalogImportAllButton.disabled = true;
    catalogSearchFeedback.textContent = "Importing results...";
    let added = 0;
    let skipped = 0;
    let failure = null;
    for (const [index, anime] of catalogSearchResultsData.entries()) {
        const button = catalogSearchResults.children[index]?.querySelector(".catalog-add-button");
        if (animeList.some((saved) => saved.title.toLocaleLowerCase() === anime.title.toLocaleLowerCase())) {
            skipped += 1;
            if (button) {
                button.disabled = true;
                button.textContent = "Already added";
            }
            continue;
        }
        try {
            await saveCatalogAnime(anime);
            added += 1;
            if (button) {
                button.disabled = true;
                button.textContent = "Added";
            }
        } catch (error) {
            if (error.status === 409) {
                skipped += 1;
                if (button) {
                    button.disabled = true;
                    button.textContent = "Already added";
                }
                continue;
            }
            failure = error;
            break;
        }
    }
    if (added) {
        renderHero();
        renderGenreFilters();
        renderCatalog();
    }
    catalogSearchFeedback.textContent = failure
        ? `${added} added, ${skipped} already in your collection. Stopped: ${failure.message}`
        : `${added} added${skipped ? `, ${skipped} already in your collection` : ""}.`;
    catalogImportAllButton.disabled = false;
});

catalogSearchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = catalogSearchInput.value.trim();
    if (query.length < 2) return;
    const searchButton = catalogSearchForm.querySelector('[type="submit"]');
    searchButton.disabled = true;
    catalogSearchFeedback.textContent = "Searching AniList...";
    catalogSearchResults.replaceChildren();
    catalogImportAllButton.hidden = true;
    try {
        const results = await api.request(`/catalog/search?q=${encodeURIComponent(query)}`);
        renderCatalogSearchResults(results);
    } catch (error) {
        console.error("Could not search AniList:", error);
        catalogSearchFeedback.textContent = error.message;
    } finally {
        searchButton.disabled = false;
    }
});

animeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = animeForm.querySelector('[type="submit"]');
    const fields = new FormData(animeForm);
    const anime = {
        title: fields.get("title").trim(),
        genre: fields.get("genre").trim(),
        description: fields.get("description").trim(),
        studio: fields.get("studio").trim() || null,
        released_date: fields.get("released_date") || null,
        cover_image: fields.get("cover_image").trim() || null,
        rating: fields.get("rating") === "" ? null : Number(fields.get("rating")),
        episode: fields.get("episode") === "" ? null : Number(fields.get("episode")),
    };

    submit.disabled = true;
    animeFormFeedback.textContent = "Adding your title...";
    try {
        const created = await api.request("/anime", { method: "POST", body: JSON.stringify(anime) });
        animeList.push(created);
        animeDialog.close();
        renderHero();
        renderGenreFilters();
        renderCatalog();
        window.location.href = `/anime-detail.html?id=${encodeURIComponent(created.id)}`;
    } catch (error) {
        console.error("Could not add anime:", error);
        animeFormFeedback.textContent = error.message;
    } finally {
        submit.disabled = false;
    }
});

searchInput.addEventListener("input", () => {
    leaveSemanticSearch();
    if (catalogMode === "collection") {
        renderCatalog();
        return;
    }
    if (catalogMode !== "browse") return;
    window.clearTimeout(externalSearchTimer);
    externalSearchTimer = window.setTimeout(() => loadExternalCatalog(1), 350);
});
sortSelect.addEventListener("change", () => {
    leaveSemanticSearch();
    renderCatalog();
});
watchlistToggle.addEventListener("click", () => {
    leaveSemanticSearch();
    if (catalogMode !== "collection") setCatalogMode("collection");
    showingWatchlist = !showingWatchlist;
    updateWatchlistButton();
    renderCatalog();
});
document.querySelectorAll("[data-catalog-mode]").forEach((button) => {
    button.addEventListener("click", () => setCatalogMode(button.dataset.catalogMode));
});
document.getElementById("apply-discovery-filters").addEventListener("click", () => loadExternalCatalog(1));
document.getElementById("catalog-prev").addEventListener("click", () => {
    if (externalCatalogPage > 1) loadExternalCatalog(externalCatalogPage - 1);
});
document.getElementById("catalog-next").addEventListener("click", () => {
    if (externalCatalogHasNext) loadExternalCatalog(externalCatalogPage + 1);
});
addAnimeButton.addEventListener("click", showAnimeForm);
document.getElementById("anime-dialog-close").addEventListener("click", () => animeDialog.close());
animeDialog.addEventListener("click", (event) => {
    if (event.target === animeDialog) animeDialog.close();
});
document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
        event.preventDefault();
        searchInput.focus();
    }
    if (event.key === "Escape" && document.activeElement === searchInput) searchInput.blur();
});

api.getToken() && (addAnimeButton.hidden = false);
populateDiscoveryFilters();
loadAnime();
