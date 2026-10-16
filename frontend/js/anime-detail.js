const api = window.AnimeHubApi;
const FAVORITE_CACHE_KEY = "anime-hub-watchlist";
const detailRoot = document.getElementById("anime-detail");
const commentList = document.getElementById("comment-list");
const commentForm = document.getElementById("comment-form");
const commentSignIn = document.getElementById("comment-sign-in");
const commentFeedback = document.getElementById("comments-feedback");
const commentCount = document.getElementById("comment-count");
const commentIsSpoiler = document.getElementById("comment-is-spoiler");
const commentSpoilerEpisodeWrap = document.getElementById("comment-spoiler-episode-wrap");
const commentSpoilerEpisode = document.getElementById("comment-spoiler-episode");
const editDialog = document.getElementById("detail-edit-dialog");
const editForm = document.getElementById("detail-edit-form");
const editFeedback = document.getElementById("detail-edit-feedback");
const animeId = new URLSearchParams(window.location.search).get("id");
let currentUser = null;

function safeImageUrl(value) {
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

function createDetailPosterPlaceholder(title, genre) {
    const placeholder = document.createElement("div");
    placeholder.className = "detail-poster poster-placeholder";
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

function setDetailState(message) {
    const state = document.createElement("div");
    state.className = "detail-state";
    state.setAttribute("role", "status");
    state.textContent = message;
    detailRoot.replaceChildren(state);
}

function addFact(facts, label, value) {
    if (value === null || value === undefined || value === "") return;
    const item = document.createElement("div");
    item.className = "fact";
    const heading = document.createElement("span");
    heading.className = "fact-label";
    heading.textContent = label;
    const text = document.createElement("span");
    text.className = "fact-value";
    text.textContent = String(value);
    item.append(heading, text);
    facts.append(item);
}

function createAniListLink(label, url, className = "") {
    if (typeof url !== "string" || !url.startsWith("https://anilist.co/")) return null;
    const link = document.createElement("a");
    link.className = className;
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = label;
    return link;
}

function renderAniListDetails(details) {
    const section = document.createElement("section");
    section.className = "anilist-details";
    section.setAttribute("aria-labelledby", "anilist-details-title");
    const heading = document.createElement("div");
    const kicker = document.createElement("p");
    kicker.className = "detail-kicker";
    kicker.textContent = "ANILIST DETAILS";
    const title = document.createElement("h2");
    title.id = "anilist-details-title";
    title.textContent = "Connected stories & credits";
    heading.append(kicker, title);
    section.append(heading);

    const groups = [
        {
            title: "Relations",
            items: details.relations,
            createItem(item) {
                const name = item.title;
                const kind = [item.relation?.replaceAll("_", " ").toLowerCase(), item.format].filter(Boolean).join(" · ");
                const link = createAniListLink(name, item.url, "anilist-relation-link");
                if (!link) return null;
                const card = document.createElement("article");
                card.className = "anilist-relation";
                const label = document.createElement("span");
                label.className = "anilist-credit-meta";
                label.textContent = kind;
                card.append(label, link);
                return card;
            },
        },
        {
            title: "Studios",
            items: details.studios,
            createItem(item) {
                return createAniListLink(
                    `${item.name}${item.is_animation_studio ? " · Animation" : ""}`,
                    item.url,
                    "anilist-credit-link",
                );
            },
        },
        {
            title: "Staff",
            items: details.staff,
            createItem(item) {
                const link = createAniListLink(item.name, item.url, "anilist-credit-link");
                if (!link) return null;
                const entry = document.createElement("div");
                entry.className = "anilist-credit";
                const role = document.createElement("span");
                role.className = "anilist-credit-meta";
                role.textContent = item.role || "Staff";
                entry.append(link, role);
                return entry;
            },
        },
        {
            title: "Characters",
            items: details.characters,
            createItem(item) {
                const link = createAniListLink(item.name, item.url, "anilist-credit-link");
                if (!link) return null;
                const entry = document.createElement("div");
                entry.className = "anilist-credit anilist-character-credit";
                const imageUrl = safeImageUrl(item.image);
                if (imageUrl) {
                    const image = document.createElement("img");
                    image.className = "anilist-character-image";
                    image.src = imageUrl;
                    image.alt = "";
                    image.loading = "lazy";
                    entry.append(image);
                }
                const role = document.createElement("span");
                role.className = "anilist-credit-meta";
                role.textContent = item.role || "Character";
                const text = document.createElement("div");
                text.className = "anilist-character-text";
                text.append(link, role);
                entry.append(text);
                return entry;
            },
        },
    ];

    groups.forEach((group) => {
        if (!Array.isArray(group.items) || !group.items.length) return;
        const panel = document.createElement("section");
        panel.className = "anilist-credit-group";
        const title = document.createElement("h3");
        title.textContent = group.title;
        const list = document.createElement("div");
        list.className = group.title === "Relations" ? "anilist-relations-list" : "anilist-credit-list";
        group.items.forEach((item) => {
            const element = group.createItem(item);
            if (element) list.append(element);
        });
        if (list.childElementCount) {
            panel.append(title, list);
            section.append(panel);
        }
    });
    return section;
}

async function loadAniListDetails(anime) {
    const match = typeof anime.source_url === "string"
        ? anime.source_url.match(/^https:\/\/anilist\.co\/anime\/(\d+)\/?$/i)
        : null;
    if (!match) return;

    const section = document.createElement("section");
    section.className = "anilist-details";
    section.setAttribute("role", "status");
    section.textContent = "Loading connected stories and credits...";
    detailRoot.append(section);
    try {
        const details = await api.request(`/catalog/anime/${match[1]}/details`);
        section.replaceWith(renderAniListDetails(details));
    } catch (error) {
        console.error("Could not load AniList relations and credits:", error);
        section.textContent = "Relations and credits are temporarily unavailable.";
    }
}

function createProgressTracker(anime) {
    const section = document.createElement("section");
    section.className = "progress-tracker";
    const heading = document.createElement("h2");
    heading.textContent = "Your watch progress";
    section.append(heading);
    if (!api.getToken()) {
        const message = document.createElement("p");
        message.textContent = "Sign in to track episodes and update your watch status.";
        const signIn = document.createElement("a");
        signIn.href = "/login.html";
        signIn.textContent = "Sign in";
        section.append(message, signIn);
        return section;
    }

    const form = document.createElement("form");
    form.className = "progress-form";
    const statusLabel = document.createElement("label");
    statusLabel.textContent = "Status";
    const status = document.createElement("select");
    status.name = "status";
    [
        ["plan_to_watch", "Plan to watch"],
        ["watching", "Watching"],
        ["completed", "Completed"],
        ["on_hold", "On hold"],
        ["dropped", "Dropped"],
    ].forEach(([value, label]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        status.append(option);
    });
    statusLabel.append(status);

    const episodesLabel = document.createElement("label");
    episodesLabel.textContent = "Episodes watched";
    const episodes = document.createElement("input");
    episodes.name = "episodes_watched";
    episodes.type = "number";
    episodes.min = "0";
    episodes.step = "1";
    if (anime.episode) episodes.max = String(anime.episode);
    episodes.value = "0";
    episodesLabel.append(episodes);

    const submit = document.createElement("button");
    submit.className = "detail-button";
    submit.type = "submit";
    submit.textContent = "Save progress";
    const remove = document.createElement("button");
    remove.className = "detail-button secondary";
    remove.type = "button";
    remove.textContent = "Remove tracking";
    remove.hidden = true;
    const feedback = document.createElement("p");
    feedback.className = "progress-feedback";
    feedback.setAttribute("role", "status");
    form.append(statusLabel, episodesLabel, submit, remove);
    section.append(form, feedback);

    api.request("/users/me/progress").then((items) => {
        const saved = items.find((item) => item.anime_id === anime.id);
        if (!saved) return;
        status.value = saved.status;
        episodes.value = String(saved.episodes_watched);
        remove.hidden = false;
    }).catch((error) => {
        console.error("Could not load watch progress:", error);
        feedback.textContent = error.message;
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        submit.disabled = true;
        feedback.textContent = "Saving progress...";
        try {
            const saved = await api.request(`/users/me/progress/${anime.id}`, {
                method: "PUT",
                body: JSON.stringify({
                    status: status.value,
                    episodes_watched: Number(episodes.value),
                }),
            });
            episodes.value = String(saved.episodes_watched);
            feedback.textContent = "Watch progress saved.";
            remove.disabled = false;
            remove.hidden = false;
        } catch (error) {
            console.error("Could not save watch progress:", error);
            feedback.textContent = error.message;
        } finally {
            submit.disabled = false;
        }
    });
    remove.addEventListener("click", async () => {
        remove.disabled = true;
        try {
            await api.request(`/users/me/progress/${anime.id}`, { method: "DELETE" });
            status.value = "plan_to_watch";
            episodes.value = "0";
            remove.hidden = true;
            remove.disabled = false;
            feedback.textContent = "Watch tracking removed.";
        } catch (error) {
            console.error("Could not remove watch tracking:", error);
            feedback.textContent = error.message;
            remove.disabled = false;
        }
    });
    return section;
}

async function updateFavoriteButton(button, id) {
    if (!api.getToken()) {
        let saved = [];
        try {
            saved = JSON.parse(localStorage.getItem(FAVORITE_CACHE_KEY) || "[]");
        } catch (error) {
            console.error("Could not read the guest watchlist:", error);
        }
        button.classList.toggle("is-saved", saved.includes(id));
        button.setAttribute("aria-pressed", String(saved.includes(id)));
        button.textContent = saved.includes(id) ? "♥  Saved to watchlist" : "♡  Add to watchlist";
        return;
    }

    const favorites = await api.request("/users/me/favorites");
    const saved = favorites.some((anime) => anime.id === id);
    button.classList.toggle("is-saved", saved);
    button.setAttribute("aria-pressed", String(saved));
    button.textContent = saved ? "♥  Saved to watchlist" : "♡  Add to watchlist";
}

function renderAnime(anime) {
    const layout = document.createElement("article");
    layout.className = "detail-layout";

    const posterWrap = document.createElement("div");
    posterWrap.className = "detail-poster-wrap";
    const src = safeImageUrl(anime.cover_image);
    if (src) {
        const poster = document.createElement("img");
        poster.className = "detail-poster";
        poster.alt = `${anime.title} cover`;
        poster.loading = "eager";
        poster.src = src;
        poster.addEventListener("error", () => {
            poster.replaceWith(createDetailPosterPlaceholder(anime.title, anime.genre));
        }, { once: true });
        posterWrap.append(poster);
    } else {
        posterWrap.append(createDetailPosterPlaceholder(anime.title, anime.genre));
    }

    const copy = document.createElement("div");
    copy.className = "detail-copy";
    const kicker = document.createElement("p");
    kicker.className = "detail-kicker";
    kicker.textContent = anime.studio || "Anime details";
    const title = document.createElement("h1");
    title.textContent = anime.title || "Untitled anime";
    copy.append(kicker, title);

    const ratingValue = anime.rating === null || anime.rating === undefined || anime.rating === "" ? null : Number(anime.rating);
    if (ratingValue !== null && Number.isFinite(ratingValue)) {
        const rating = document.createElement("p");
        rating.className = "detail-rating";
        const star = document.createElement("span");
        star.textContent = "★";
        const score = document.createElement("strong");
        score.textContent = ratingValue.toFixed(1);
        const outOf = document.createElement("span");
        outOf.textContent = " / 10";
        rating.append(star, score, outOf);
        copy.append(rating);
    }

    const genres = (anime.genre || "").split(",").map((genre) => genre.trim()).filter(Boolean);
    if (genres.length) {
        const genreList = document.createElement("div");
        genreList.className = "genre-list";
        genreList.setAttribute("aria-label", "Genres");
        genres.forEach((genre) => {
            const tag = document.createElement("span");
            tag.className = "genre-tag";
            tag.textContent = genre;
            genreList.append(tag);
        });
        copy.append(genreList);
    }

    const description = document.createElement("p");
    description.className = "detail-summary";
    description.textContent = anime.description || "No synopsis is available for this title yet.";
    copy.append(description);

    const facts = document.createElement("div");
    facts.className = "detail-facts";
    addFact(facts, "STUDIO", anime.studio);
    addFact(facts, "EPISODES", anime.episode);
    addFact(facts, "RELEASE DATE", anime.released_date);
    addFact(facts, "ADDED BY", anime.user_id ? "Community member" : "Anime Hub");
    copy.append(facts);
    if (anime.source_url) {
        const source = document.createElement("a");
        source.className = "external-source";
        source.href = anime.source_url;
        source.target = "_blank";
        source.rel = "noreferrer";
        source.textContent = "Metadata and artwork via AniList ↗";
        copy.append(source);
    }

    const actions = document.createElement("div");
    actions.className = "detail-actions";
    const detailFeedback = document.createElement("p");
    detailFeedback.className = "detail-feedback";
    detailFeedback.setAttribute("role", "status");
    const favorite = document.createElement("button");
    favorite.className = "detail-button";
    favorite.type = "button";
    favorite.addEventListener("click", async () => {
        favorite.disabled = true;
        try {
            if (api.getToken()) {
                const saved = favorite.getAttribute("aria-pressed") === "true";
                await api.request(`/users/me/favorites/${anime.id}`, { method: saved ? "DELETE" : "POST" });
            } else {
                let saved = [];
                try {
                    saved = JSON.parse(localStorage.getItem(FAVORITE_CACHE_KEY) || "[]");
                } catch (error) {
                    console.error("Could not read the guest watchlist:", error);
                }
                const updated = saved.includes(anime.id)
                    ? saved.filter((id) => id !== anime.id)
                    : [...saved, anime.id];
                localStorage.setItem(FAVORITE_CACHE_KEY, JSON.stringify(updated));
            }
            await updateFavoriteButton(favorite, anime.id);
            commentFeedback.textContent = "";
        } catch (error) {
            console.error("Could not update the watchlist:", error);
            commentFeedback.textContent = error.message;
        } finally {
            favorite.disabled = false;
        }
    });
    updateFavoriteButton(favorite, anime.id).catch((error) => {
        console.error("Could not load the watchlist:", error);
        if (error.status === 401) api.clearToken();
        favorite.textContent = "♡  Add to watchlist";
    });
    actions.append(favorite);
    if (currentUser && anime.user_id === currentUser.id) {
        const edit = document.createElement("button");
        edit.className = "detail-button secondary";
        edit.type = "button";
        edit.textContent = "Edit title";
        edit.addEventListener("click", () => openEditForm(anime));
        const remove = document.createElement("button");
        remove.className = "detail-button danger";
        remove.type = "button";
        remove.textContent = "Delete title";
        remove.addEventListener("click", async () => {
            if (!window.confirm(`Delete "${anime.title}"? This also removes its comments and favorites.`)) return;
            remove.disabled = true;
            try {
                await api.request(`/anime/${anime.id}`, { method: "DELETE" });
                window.location.assign("/");
            } catch (error) {
                console.error("Could not delete the anime:", error);
                detailFeedback.textContent = error.message;
                remove.disabled = false;
            }
        });
        actions.append(edit, remove);
    }
    copy.append(actions, detailFeedback, createProgressTracker(anime));

    layout.append(posterWrap, copy);
    detailRoot.replaceChildren(layout);
    document.title = `${anime.title} — Anime Hub`;
}

function openEditForm(anime) {
    for (const field of ["title", "genre", "studio", "rating", "episode", "released_date", "cover_image", "description"]) {
        const value = anime[field];
        editForm.elements[field].value = value === null || value === undefined ? "" : value;
    }
    editFeedback.textContent = "";
    editDialog.showModal();
}

function renderComments(comments) {
    commentCount.textContent = `${comments.length} ${comments.length === 1 ? "comment" : "comments"}`;
    if (!comments.length) {
        const empty = document.createElement("p");
        empty.className = "profile-empty";
        empty.textContent = "No comments yet. Start the conversation.";
        commentList.replaceChildren(empty);
        return;
    }

    commentList.replaceChildren(...comments.map((comment) => {
        const card = document.createElement("article");
        card.className = "comment-card";
        const heading = document.createElement("div");
        heading.className = "comment-card-heading";
        const identity = document.createElement("div");
        const name = document.createElement("span");
        name.className = "comment-author";
        name.textContent = comment.user_name;
        identity.append(name);
        if (comment.created_at) {
            const date = document.createElement("time");
            date.className = "comment-date";
            date.dateTime = comment.created_at;
            date.textContent = new Date(comment.created_at).toLocaleDateString();
            identity.append(date);
        }
        heading.append(identity);
        if (comment.is_spoiler) {
            const spoilerLabel = document.createElement("span");
            spoilerLabel.className = "comment-spoiler-label";
            spoilerLabel.textContent = comment.is_revealed
                ? `Spoiler · Episode ${comment.spoiler_episode}`
                : `Hidden spoiler · Episode ${comment.spoiler_episode}`;
            identity.append(spoilerLabel);
        }
        if (currentUser && currentUser.id === comment.user_id) {
            const remove = document.createElement("button");
            remove.className = "comment-delete";
            remove.type = "button";
            remove.textContent = "Delete";
            remove.addEventListener("click", () => deleteComment(comment.id));
            heading.append(remove);
        }
        const text = document.createElement("p");
        text.className = "comment-body";
        text.textContent = comment.comment;
        card.append(heading, text);
        return card;
    }));
}

async function loadComments() {
    try {
        const comments = await api.request(`/anime/${animeId}/comments`);
        renderComments(comments);
        if (api.getToken() && !currentUser) {
            try {
                currentUser = await api.request("/auth/me");
            } catch (error) {
                if (error.status === 401) api.clearToken();
                else throw error;
            }
        }
        commentForm.hidden = !api.getToken();
        commentSignIn.hidden = Boolean(api.getToken());
        if (currentUser) renderComments(comments);
    } catch (error) {
        console.error("Could not load comments:", error);
        commentFeedback.textContent = error.message;
    }
}

editForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = editForm.querySelector('[type="submit"]');
    const fields = new FormData(editForm);
    const changes = {
        title: fields.get("title").trim(),
        genre: fields.get("genre").trim(),
        studio: fields.get("studio").trim() || null,
        rating: fields.get("rating") === "" ? null : Number(fields.get("rating")),
        episode: fields.get("episode") === "" ? null : Number(fields.get("episode")),
        released_date: fields.get("released_date") || null,
        cover_image: fields.get("cover_image").trim() || null,
        description: fields.get("description").trim(),
    };
    submit.disabled = true;
    editFeedback.textContent = "Saving changes...";
    try {
        const updated = await api.request(`/anime/${animeId}`, {
            method: "PATCH",
            body: JSON.stringify(changes),
        });
        editDialog.close();
        renderAnime(updated);
        document.title = `${updated.title} — Anime Hub`;
    } catch (error) {
        console.error("Could not update the anime:", error);
        editFeedback.textContent = error.message;
    } finally {
        submit.disabled = false;
    }
});

document.getElementById("detail-edit-close").addEventListener("click", () => editDialog.close());
editDialog.addEventListener("click", (event) => {
    if (event.target === editDialog) editDialog.close();
});

async function deleteComment(commentId) {
    try {
        await api.request(`/comments/${commentId}`, { method: "DELETE" });
        await loadComments();
    } catch (error) {
        console.error("Could not delete the comment:", error);
        commentFeedback.textContent = error.message;
    }
}

commentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = commentForm.querySelector('[type="submit"]');
    const comment = commentForm.elements.comment.value.trim();
    if (!comment) return;
    const isSpoiler = commentIsSpoiler.checked;
    const spoilerEpisode = Number(commentSpoilerEpisode.value);
    if (isSpoiler && (!Number.isInteger(spoilerEpisode) || spoilerEpisode < 1)) {
        commentFeedback.textContent = "Enter the episode number your comment spoils.";
        commentSpoilerEpisode.focus();
        return;
    }
    submit.disabled = true;
    commentFeedback.textContent = "Posting your comment...";
    try {
        await api.request(`/anime/${animeId}/comments`, {
            method: "POST",
            body: JSON.stringify({
                comment,
                is_spoiler: isSpoiler,
                spoiler_episode: isSpoiler ? spoilerEpisode : null,
            }),
        });
        commentForm.reset();
        commentFeedback.textContent = "";
        await loadComments();
    } catch (error) {
        console.error("Could not post your comment:", error);
        commentFeedback.textContent = error.message;
    } finally {
        submit.disabled = false;
    }
});

commentIsSpoiler.addEventListener("change", () => {
    commentSpoilerEpisodeWrap.hidden = !commentIsSpoiler.checked;
    commentSpoilerEpisode.disabled = !commentIsSpoiler.checked;
    commentSpoilerEpisode.required = commentIsSpoiler.checked;
    if (!commentIsSpoiler.checked) commentSpoilerEpisode.value = "";
});

async function loadAnimeDetail() {
    if (!animeId || !/^\d+$/.test(animeId)) {
        setDetailState("That anime link is missing a valid title ID.");
        return;
    }

    try {
        const anime = await api.request(`/anime/${encodeURIComponent(animeId)}`);
        if (api.getToken()) {
            try {
                currentUser = await api.request("/auth/me");
            } catch (error) {
                if (error.status === 401) api.clearToken();
                else throw error;
            }
        }
        renderAnime(anime);
        loadAniListDetails(anime);
        await loadComments();
    } catch (error) {
        console.error("Failed to load anime details:", error);
        setDetailState(error.status === 404
            ? "We couldn't find that anime. It may have been removed."
            : "Anime details couldn't be loaded. Please go back and try again.");
    }
}

loadAnimeDetail();
