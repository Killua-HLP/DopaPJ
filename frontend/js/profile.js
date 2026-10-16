const api = window.AnimeHubApi;
const profileFeedback = document.getElementById("profile-feedback");
const profileContent = document.getElementById("profile-content");
const profileForm = document.getElementById("profile-form");
const formFeedback = document.getElementById("profile-form-feedback");
const profileImageInput = document.getElementById("profile-image-file");
const profileImageUpload = document.getElementById("profile-image-upload");
const profileImageFeedback = document.getElementById("profile-image-feedback");
const passwordForm = document.getElementById("password-form");
const passwordFeedback = document.getElementById("password-feedback");
const createdList = document.getElementById("profile-created");
const queueList = document.getElementById("profile-queue");
const queueFeedback = document.getElementById("profile-queue-feedback");
const tasteMap = document.getElementById("profile-taste");
const airingList = document.getElementById("profile-airing");
const recapContainer = document.getElementById("profile-recap");
const recapYear = document.getElementById("profile-recap-year");
const libraryGrid = document.getElementById("profile-library-grid");
const libraryCount = document.getElementById("profile-library-count");
let profileLibrary = { favorites: [], progress: [] };
let activeLibraryFilter = "all";

function setListMessage(container, message) {
    const text = document.createElement("p");
    text.className = "profile-empty";
    text.textContent = message;
    container.replaceChildren(text);
}

function profileImageUrl(value) {
    const source = String(value || "").trim();
    if (!source || source.toLowerCase() === "string") return "";
    if (/^https?:\/\//i.test(source)) return source;
    if (source.startsWith("/static/") || source.startsWith("/uploads/")) return source;
    return `/static/${source.replace(/^\/+/, "")}`;
}

function createProfilePosterPlaceholder(title) {
    const placeholder = document.createElement("div");
    placeholder.className = "profile-thumbnail poster-placeholder";
    placeholder.setAttribute("aria-label", `${title} cover unavailable`);
    const heading = document.createElement("strong");
    heading.className = "placeholder-title";
    heading.textContent = title;
    placeholder.append(heading);
    return placeholder;
}

function renderAnimeList(container, items, emptyMessage) {
    if (!items.length) {
        setListMessage(container, emptyMessage);
        return;
    }
    container.replaceChildren(...items.map((anime) => {
        const item = document.createElement("article");
        item.className = "profile-anime-item";
        const cover = profileImageUrl(anime.cover_image);
        let thumbnail;
        if (cover) {
            const image = document.createElement("img");
            image.alt = "";
            image.loading = "lazy";
            image.src = cover;
            image.addEventListener("error", () => {
                image.replaceWith(createProfilePosterPlaceholder(anime.title));
            }, { once: true });
            thumbnail = image;
        } else {
            thumbnail = createProfilePosterPlaceholder(anime.title);
        }
        const copy = document.createElement("div");
        const link = document.createElement("a");
        link.href = `/anime-detail.html?id=${encodeURIComponent(anime.id)}`;
        link.textContent = anime.title;
        const genre = document.createElement("span");
        genre.textContent = anime.genre;
        copy.append(link, genre);
        item.append(thumbnail, copy);
        return item;
    }));
}

function renderLibrary() {
    const savedById = new Map(profileLibrary.favorites.map((anime) => [anime.id, anime]));
    const library = new Map();
    profileLibrary.progress.forEach((item) => {
        library.set(item.anime_id, { anime: item.anime, progress: item });
    });
    profileLibrary.favorites.forEach((anime) => {
        if (!library.has(anime.id)) library.set(anime.id, { anime, progress: null });
    });

    const filtered = [...library.values()].filter(({ anime, progress }) => {
        if (activeLibraryFilter === "all") return true;
        if (activeLibraryFilter === "saved") return savedById.has(anime.id);
        return progress?.status === activeLibraryFilter;
    });
    const tabCounts = {
        watching: profileLibrary.progress.filter((item) => item.status === "watching").length,
        plan_to_watch: profileLibrary.progress.filter((item) => item.status === "plan_to_watch").length,
        completed: profileLibrary.progress.filter((item) => item.status === "completed").length,
        saved: profileLibrary.favorites.length,
        all: library.size,
    };
    Object.entries(tabCounts).forEach(([filter, count]) => {
        const element = document.getElementById(`count-${filter}`);
        if (element) element.textContent = String(count);
    });
    document.querySelectorAll("[data-library-filter]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.libraryFilter === activeLibraryFilter));
    });
    libraryCount.textContent = `${filtered.length} ${filtered.length === 1 ? "title" : "titles"}`;
    if (!filtered.length) {
        const empty = document.createElement("p");
        empty.className = "profile-library-empty";
        empty.textContent = activeLibraryFilter === "all"
            ? "Your library is empty. Discover anime and save titles or track your progress."
            : "No titles in this section yet.";
        libraryGrid.replaceChildren(empty);
        return;
    }

    const statusLabels = {
        plan_to_watch: "To watch",
        watching: "Watching",
        completed: "Watched",
        on_hold: "On hold",
        dropped: "Dropped",
    };
    libraryGrid.replaceChildren(...filtered.map(({ anime, progress }) => {
        const card = document.createElement("a");
        card.className = "profile-library-card";
        card.href = `/anime-detail.html?id=${encodeURIComponent(anime.id)}`;
        const cover = profileImageUrl(anime.cover_image);
        if (cover) {
            const image = document.createElement("img");
            image.alt = "";
            image.loading = "lazy";
            image.src = cover;
            image.addEventListener("error", () => image.replaceWith(
                createProfilePosterPlaceholder(anime.title),
            ), { once: true });
            card.append(image);
        } else {
            card.append(createProfilePosterPlaceholder(anime.title));
        }
        const badge = document.createElement("span");
        badge.className = `profile-library-badge${progress ? ` is-${progress.status}` : ""}`;
        badge.textContent = progress ? statusLabels[progress.status] || progress.status : "Saved";
        const copy = document.createElement("span");
        copy.className = "profile-library-copy";
        const title = document.createElement("strong");
        title.textContent = anime.title;
        const genre = document.createElement("span");
        genre.textContent = [anime.genre || "Anime", progress ? `${progress.episodes_watched} eps` : ""]
            .filter(Boolean)
            .join(" · ");
        copy.append(title, genre);
        card.append(badge, copy);
        return card;
    }));
}

function renderQueue(items) {
    const queue = items
        .filter((item) => item.status === "plan_to_watch")
        .sort((first, second) => (
            (first.queue_position ?? Number.MAX_SAFE_INTEGER) - (second.queue_position ?? Number.MAX_SAFE_INTEGER)
            || first.anime.title.localeCompare(second.anime.title)
        ));
    if (!queue.length) {
        setListMessage(queueList, "Mark a title as plan to watch to build your queue.");
        return;
    }
    queueList.replaceChildren(...queue.map((progress, index) => {
        const row = document.createElement("article");
        row.className = "profile-anime-item profile-queue-item";
        const position = document.createElement("span");
        position.className = "queue-position";
        position.textContent = String(index + 1).padStart(2, "0");
        const copy = document.createElement("div");
        const title = document.createElement("a");
        title.href = `/anime-detail.html?id=${encodeURIComponent(progress.anime_id)}`;
        title.textContent = progress.anime.title;
        const genres = document.createElement("span");
        genres.textContent = progress.anime.genre || "Anime";
        copy.append(title, genres);
        const controls = document.createElement("div");
        controls.className = "queue-controls";
        [
            { label: "Move up", symbol: "↑", disabled: index === 0, target: index - 1 },
            { label: "Move down", symbol: "↓", disabled: index === queue.length - 1, target: index + 1 },
        ].forEach(({ label, symbol, disabled, target }) => {
            const button = document.createElement("button");
            button.className = "queue-move";
            button.type = "button";
            button.textContent = symbol;
            button.setAttribute("aria-label", `${label}: ${progress.anime.title}`);
            button.disabled = disabled;
            button.addEventListener("click", () => moveQueueItem(queue, index, target));
            controls.append(button);
        });
        row.append(position, copy, controls);
        return row;
    }));
}

async function moveQueueItem(queue, from, to) {
    const reordered = [...queue];
    const [item] = reordered.splice(from, 1);
    reordered.splice(to, 0, item);
    queueFeedback.textContent = "Updating your queue...";
    try {
        const items = await api.request("/users/me/progress/queue", {
            method: "PATCH",
            body: JSON.stringify({ anime_ids: reordered.map((entry) => entry.anime_id) }),
        });
        profileLibrary.progress = items;
        renderQueue(items);
        renderLibrary();
        queueFeedback.textContent = "Queue order saved.";
    } catch (error) {
        console.error("Could not reorder watch queue:", error);
        queueFeedback.textContent = error.message;
    }
}

function renderTasteMap(favorites, progress) {
    const savedById = new Map(favorites.map((anime) => [anime.id, anime]));
    progress.forEach((item) => savedById.set(item.anime.id, item.anime));
    const genres = new Map();
    const studios = new Map();
    savedById.forEach((anime) => {
        (anime.genre || "").split(",").map((value) => value.trim()).filter(Boolean).forEach((genre) => {
            genres.set(genre, (genres.get(genre) || 0) + 1);
        });
        if (anime.studio) studios.set(anime.studio, (studios.get(anime.studio) || 0) + 1);
    });
    if (!savedById.size) {
        setListMessage(tasteMap, "Save favorites or track anime to reveal your taste map.");
        return;
    }
    tasteMap.replaceChildren();
    const makeGroup = (label, counts) => {
        const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
        const group = document.createElement("section");
        group.className = "taste-group";
        const heading = document.createElement("h3");
        heading.textContent = label;
        group.append(heading);
        sorted.forEach(([value, count], index) => {
            const row = document.createElement("div");
            row.className = "taste-row";
            const text = document.createElement("span");
            text.textContent = value;
            const bar = document.createElement("span");
            bar.className = "taste-bar";
            const fill = document.createElement("span");
            fill.style.width = `${Math.max(16, 100 - index * 16)}%`;
            bar.append(fill);
            const amount = document.createElement("strong");
            amount.textContent = String(count);
            row.append(text, bar, amount);
            group.append(row);
        });
        return group;
    };
    tasteMap.append(makeGroup("Favorite genres", genres), makeGroup("Studios you return to", studios));
}

function renderAiring(response) {
    if (!response.results.length) {
        setListMessage(airingList, response.message || "No upcoming episodes found for your list.");
        return;
    }
    airingList.replaceChildren(...response.results.map((anime) => {
        const row = document.createElement("article");
        row.className = "profile-anime-item airing-item";
        const details = document.createElement("div");
        const title = document.createElement("a");
        title.href = `/anime-detail.html?id=${encodeURIComponent(anime.local_anime_id)}`;
        title.textContent = anime.title;
        const next = document.createElement("span");
        const date = new Date(anime.next_episode.airing_at * 1000);
        next.textContent = `Episode ${anime.next_episode.episode} · ${new Intl.DateTimeFormat(undefined, {
            dateStyle: "medium",
            timeStyle: "short",
        }).format(date)}`;
        details.append(title, next);
        row.append(details);
        return row;
    }));
}

function renderRecap(recap) {
    recapContainer.replaceChildren();
    const hero = document.createElement("div");
    hero.className = "recap-hero";
    const heroCopy = document.createElement("div");
    heroCopy.className = "recap-hero-copy";
    const eyebrow = document.createElement("p");
    eyebrow.className = "eyebrow";
    eyebrow.textContent = "YOUR YEAR IN ANIME";
    const heading = document.createElement("h3");
    heading.textContent = recap.completed_count
        ? `${recap.year}, in stories.`
        : `Your ${recap.year} story starts here.`;
    const summary = document.createElement("p");
    summary.textContent = recap.completed_count
        ? `You completed ${recap.completed_count} ${recap.completed_count === 1 ? "title" : "titles"} this year. Here's a look back at what you tracked.`
        : "Mark anime as completed and track episodes to build your year-in-review.";
    heroCopy.append(eyebrow, heading, summary);
    if (recap.titles[0]?.cover_image) {
        const art = document.createElement("img");
        art.className = "recap-hero-art";
        art.src = recap.titles[0].cover_image;
        art.alt = "";
        art.loading = "lazy";
        hero.append(art);
    }
    hero.append(heroCopy);

    const stats = document.createElement("div");
    stats.className = "recap-stats";
    [
        { value: recap.completed_count, label: "titles completed", accent: "violet" },
        { value: recap.episodes_watched, label: "episodes on completed titles", accent: "teal" },
        { value: recap.completion_days, label: "days with a completion", accent: "gold" },
    ].forEach(({ value, label, accent }) => {
        const stat = document.createElement("article");
        stat.className = `recap-stat recap-stat-${accent}`;
        const number = document.createElement("strong");
        number.textContent = String(value);
        const caption = document.createElement("span");
        caption.textContent = label;
        stat.append(number, caption);
        stats.append(stat);
    });

    const insights = document.createElement("div");
    insights.className = "recap-insights";
    [
        { label: "Your top genre", value: recap.top_genre || "Not enough data yet", icon: "✦" },
        { label: "Top studio", value: recap.top_studio || "Not enough data yet", icon: "◈" },
    ].forEach(({ label, value, icon }) => {
        const insight = document.createElement("div");
        insight.className = "recap-insight";
        const symbol = document.createElement("span");
        symbol.className = "recap-insight-icon";
        symbol.setAttribute("aria-hidden", "true");
        symbol.textContent = icon;
        const copy = document.createElement("div");
        const caption = document.createElement("span");
        caption.textContent = label;
        const result = document.createElement("strong");
        result.textContent = value;
        copy.append(caption, result);
        insight.append(symbol, copy);
        insights.append(insight);
    });

    const timeline = document.createElement("section");
    timeline.className = "recap-timeline";
    const timelineHeading = document.createElement("div");
    timelineHeading.className = "recap-subheading";
    const timelineTitle = document.createElement("h4");
    timelineTitle.textContent = "Your year, month by month";
    const timelineNote = document.createElement("span");
    timelineNote.textContent = "Titles completed";
    timelineHeading.append(timelineTitle, timelineNote);
    const chart = document.createElement("div");
    chart.className = "recap-month-chart";
    chart.setAttribute("role", "img");
    const monthLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const maxMonth = Math.max(1, ...recap.monthly_completions);
    chart.setAttribute(
        "aria-label",
        recap.monthly_completions.map((count, index) => `${monthLabels[index]}: ${count}`).join(", "),
    );
    recap.monthly_completions.forEach((count, index) => {
        const month = document.createElement("div");
        month.className = "recap-month";
        const value = document.createElement("span");
        value.className = "recap-month-value";
        value.textContent = count ? String(count) : "";
        const barTrack = document.createElement("div");
        barTrack.className = "recap-month-track";
        const bar = document.createElement("span");
        bar.style.height = `${count ? Math.max(8, (count / maxMonth) * 100) : 0}%`;
        barTrack.append(bar);
        const label = document.createElement("span");
        label.className = "recap-month-label";
        label.textContent = monthLabels[index];
        month.append(value, barTrack, label);
        chart.append(month);
    });
    timeline.append(timelineHeading, chart);

    const titleSection = document.createElement("section");
    titleSection.className = "recap-titles-section";
    const titleHeading = document.createElement("div");
    titleHeading.className = "recap-subheading";
    const titleLabel = document.createElement("h4");
    titleLabel.textContent = "Recently completed";
    const titleCount = document.createElement("span");
    titleCount.textContent = `Latest ${Math.min(5, recap.titles.length)} of ${recap.titles.length}`;
    titleHeading.append(titleLabel, titleCount);
    titleSection.append(titleHeading);
    if (recap.titles.length) {
        const titleGrid = document.createElement("div");
        titleGrid.className = "recap-title-grid";
        recap.titles.slice(0, 5).forEach((item) => {
            const card = document.createElement("article");
            card.className = "recap-title-card";
            if (item.cover_image) {
                const cover = document.createElement("img");
                cover.src = item.cover_image;
                cover.alt = "";
                cover.loading = "lazy";
                card.append(cover);
            } else {
                const placeholder = document.createElement("div");
                placeholder.className = "recap-title-placeholder";
                placeholder.setAttribute("aria-hidden", "true");
                placeholder.textContent = "✦";
                card.append(placeholder);
            }
            const copy = document.createElement("div");
            copy.className = "recap-title-copy";
            const name = document.createElement("strong");
            name.textContent = item.title;
            const detail = document.createElement("span");
            const completionDate = new Date(item.completed_at);
            const dateLabel = Number.isNaN(completionDate.getTime())
                ? "Completed this year"
                : `Completed ${completionDate.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
            detail.textContent = `${item.episodes_watched} ${item.episodes_watched === 1 ? "episode" : "episodes"} · ${dateLabel}`;
            copy.append(name, detail);
            card.append(copy);
            titleGrid.append(card);
        });
        titleSection.append(titleGrid);
    } else {
        const empty = document.createElement("p");
        empty.className = "recap-empty";
        empty.textContent = "Your completed titles will show up here.";
        titleSection.append(empty);
    }

    const footnote = document.createElement("p");
    footnote.className = "recap-footnote";
    footnote.textContent = "Based on titles you marked completed and episode counts recorded in Anime Hub.";
    recapContainer.append(hero, stats, insights, timeline, titleSection, footnote);
}

async function loadRecap() {
    try {
        const recap = await api.request(`/users/me/progress/recap?year=${encodeURIComponent(recapYear.value)}`);
        renderRecap(recap);
    } catch (error) {
        console.error("Could not load yearly recap:", error);
        setListMessage(recapContainer, error.message);
    }
}

async function loadProfile() {
    if (!api.getToken()) {
        window.location.replace("/login.html");
        return;
    }
    try {
        const [user, favorites, anime, progress] = await Promise.all([
            api.request("/users/me"),
            api.request("/users/me/favorites"),
            api.request("/anime"),
            api.request("/users/me/progress"),
        ]);
        document.getElementById("profile-title").textContent = user.name;
        document.getElementById("profile-avatar-initial").textContent = user.name.trim().charAt(0).toUpperCase();
        document.getElementById("profile-bio").textContent = user.bio || "Your anime collection, all in one place.";
        const avatar = document.getElementById("profile-avatar-image");
        const avatarUrl = profileImageUrl(user.cover_image);
        if (avatarUrl) {
            avatar.src = avatarUrl;
            avatar.hidden = false;
            avatar.addEventListener("error", () => { avatar.hidden = true; }, { once: true });
        } else {
            avatar.hidden = true;
        }
        profileForm.elements.name.value = user.name;
        profileForm.elements.email.value = user.email;
        profileForm.elements.bio.value = user.bio || "";
        profileForm.elements.cover_image.value = user.cover_image || "";
        document.getElementById("profile-meta").textContent = `MEMBER SINCE ${user.created_at ? new Date(user.created_at).toLocaleDateString(undefined, { month: "long", year: "numeric" }) : "RECENTLY"}`;
        const bannerAnime = progress.find((item) => item.anime.cover_image)?.anime
            || favorites.find((item) => item.cover_image);
        const banner = document.getElementById("profile-cover-art");
        const bannerUrl = profileImageUrl(bannerAnime?.cover_image);
        banner.src = bannerUrl || "/static/miyuki.jpg";
        banner.hidden = false;
        banner.classList.toggle("is-default", !bannerUrl);
        banner.addEventListener("error", () => { banner.hidden = true; }, { once: true });
        profileLibrary = { favorites, progress };
        document.getElementById("profile-stat-tracked").textContent = String(progress.length);
        document.getElementById("profile-stat-watching").textContent = String(
            progress.filter((item) => item.status === "watching").length,
        );
        document.getElementById("profile-stat-completed").textContent = String(
            progress.filter((item) => item.status === "completed").length,
        );
        document.getElementById("profile-stat-saved").textContent = String(favorites.length);
        renderLibrary();
        renderAnimeList(createdList, anime.filter((title) => title.user_id === user.id), "You haven't added any titles yet.");
        renderQueue(progress);
        renderTasteMap(favorites, progress);
        const currentYear = new Date().getFullYear();
        recapYear.replaceChildren(...Array.from({ length: 6 }, (_, index) => {
            const option = document.createElement("option");
            option.value = String(currentYear - index);
            option.textContent = String(currentYear - index);
            return option;
        }));
        recapYear.value = String(currentYear);
        const [airingResult] = await Promise.allSettled([
            api.request("/catalog/airing"),
            loadRecap(),
        ]);
        if (airingResult.status === "fulfilled") renderAiring(airingResult.value);
        else {
            console.error("Could not load airing calendar:", airingResult.reason);
            setListMessage(airingList, airingResult.reason.message || "Airing schedule is unavailable.");
        }
        profileFeedback.textContent = "";
        profileContent.hidden = false;
    } catch (error) {
        console.error("Could not load your profile:", error);
        if (error.status === 401) {
            api.clearToken();
            window.location.replace("/login.html");
            return;
        }
        profileFeedback.textContent = error.message;
    }
}

profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fields = new FormData(profileForm);
    const button = profileForm.querySelector('[type="submit"]');
    button.disabled = true;
    formFeedback.textContent = "Saving your details...";
    try {
        const user = await api.request("/users/me", {
            method: "PATCH",
            body: JSON.stringify({
                name: fields.get("name").trim(),
                bio: fields.get("bio").trim() || null,
                cover_image: fields.get("cover_image").trim() || null,
            }),
        });
        document.getElementById("profile-title").textContent = user.name;
        document.getElementById("profile-avatar-initial").textContent = user.name.trim().charAt(0).toUpperCase();
        document.getElementById("profile-bio").textContent = user.bio || "Your anime collection, all in one place.";
        const avatar = document.getElementById("profile-avatar-image");
        const avatarUrl = profileImageUrl(user.cover_image);
        avatar.hidden = !avatarUrl;
        if (avatarUrl) {
            avatar.src = avatarUrl;
            avatar.addEventListener("error", () => { avatar.hidden = true; }, { once: true });
        }
        formFeedback.textContent = "Your profile has been saved.";
    } catch (error) {
        console.error("Could not update your profile:", error);
        formFeedback.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

passwordForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fields = new FormData(passwordForm);
    const newPassword = fields.get("new_password");
    if (newPassword !== fields.get("confirm_password")) {
        passwordFeedback.textContent = "New passwords do not match.";
        return;
    }

    const button = passwordForm.querySelector('[type="submit"]');
    button.disabled = true;
    passwordFeedback.textContent = "Updating your password...";
    try {
        await api.request("/auth/change-password", {
            method: "POST",
            body: JSON.stringify({
                current_password: fields.get("current_password"),
                new_password: newPassword,
            }),
        });
        passwordForm.reset();
        passwordFeedback.textContent = "Your password has been updated.";
    } catch (error) {
        console.error("Could not update your password:", error);
        passwordFeedback.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

profileImageUpload.addEventListener("click", async () => {
    const image = profileImageInput.files[0];
    if (!image) {
        profileImageFeedback.textContent = "Choose an image file first.";
        return;
    }

    profileImageUpload.disabled = true;
    profileImageFeedback.textContent = "Uploading your picture...";
    const formData = new FormData();
    formData.append("image", image);
    try {
        const user = await api.request("/users/me/avatar", {
            method: "POST",
            body: formData,
        });
        profileForm.elements.cover_image.value = user.cover_image;
        const avatar = document.getElementById("profile-avatar-image");
        avatar.src = user.cover_image;
        avatar.hidden = false;
        avatar.addEventListener("error", () => { avatar.hidden = true; }, { once: true });
        profileImageInput.value = "";
        profileImageFeedback.textContent = "Your profile picture has been uploaded.";
    } catch (error) {
        console.error("Could not upload your profile picture:", error);
        profileImageFeedback.textContent = error.message;
    } finally {
        profileImageUpload.disabled = false;
    }
});

loadProfile();

recapYear.addEventListener("change", loadRecap);
document.querySelectorAll("[data-library-filter]").forEach((button) => {
    button.addEventListener("click", () => {
        activeLibraryFilter = button.dataset.libraryFilter;
        renderLibrary();
    });
});
