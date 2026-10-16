(function () {
    const api = window.AnimeHubApi;
    const feedback = document.getElementById("admin-feedback");
    const tableHead = document.getElementById("admin-table-head");
    const tableBody = document.getElementById("admin-table-body");
    const searchInput = document.getElementById("admin-search");
    const dialog = document.getElementById("anime-dialog");
    const form = document.getElementById("anime-form");
    const pageSize = 25;
    let activeTab = "anime";
    let currentPage = 1;
    let totalItems = 0;
    let searchTimer;

    function showFeedback(message, isError) {
        feedback.textContent = message;
        feedback.className = `admin-feedback is-visible ${isError ? "is-error" : "is-success"}`;
        window.clearTimeout(showFeedback.timer);
        showFeedback.timer = window.setTimeout(() => {
            feedback.className = "admin-feedback";
        }, 5500);
    }

    function escapeDate(value) {
        if (!value) return "—";
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    }

    function cell(content, className) {
        const element = document.createElement("td");
        if (className) element.className = className;
        if (content instanceof Node) element.append(content);
        else element.textContent = content == null || content === "" ? "—" : String(content);
        return element;
    }

    function subline(primary, secondary) {
        const wrapper = document.createElement("div");
        wrapper.textContent = primary || "—";
        if (secondary) {
            const sub = document.createElement("span");
            sub.className = "admin-table-sub";
            sub.textContent = secondary;
            wrapper.append(sub);
        }
        return wrapper;
    }

    function actionButton(label, callback, danger) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `admin-action${danger ? " is-danger" : ""}`;
        button.textContent = label;
        button.addEventListener("click", callback);
        return button;
    }

    function pill(label, variant) {
        const element = document.createElement("span");
        element.className = `admin-pill${variant ? ` ${variant}` : ""}`;
        element.textContent = label;
        return element;
    }

    function row(cells) {
        const tr = document.createElement("tr");
        for (const item of cells) tr.append(item instanceof Node ? item : cell(item));
        return tr;
    }

    function setTable(columns, rows, emptyMessage) {
        const headRow = document.createElement("tr");
        for (const column of columns) {
            const th = document.createElement("th");
            th.textContent = column;
            headRow.append(th);
        }
        tableHead.replaceChildren(headRow);
        if (!rows.length) {
            const empty = cell(emptyMessage, "admin-empty");
            empty.colSpan = columns.length;
            tableBody.replaceChildren(row([empty]));
        } else {
            tableBody.replaceChildren(...rows);
        }
    }

    async function loadOverview() {
        const data = await api.request("/admin/overview");
        document.getElementById("metric-users").textContent = data.totals.users.toLocaleString();
        document.getElementById("metric-active-users").textContent = `${data.totals.active_users.toLocaleString()} active accounts`;
        document.getElementById("metric-anime").textContent = data.totals.anime.toLocaleString();
        document.getElementById("metric-registrations").textContent = data.registrations_last_7_days.toLocaleString();
        document.getElementById("metric-pending").textContent = data.totals.pending_comments.toLocaleString();
        document.getElementById("metric-comments").textContent = `${data.totals.comments.toLocaleString()} total comments`;
        document.getElementById("metric-cache").textContent = `${data.anilist_cache.fresh}/${data.anilist_cache.entries}`;
        document.getElementById("metric-cache-stale").textContent = `${data.anilist_cache.stale} expired cache entries`;
        document.getElementById("comment-tab-count").textContent = data.totals.pending_comments.toLocaleString();
        document.getElementById("admin-last-updated").textContent = `Updated ${new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
        const icon = { registration: "↗", comment: "✎", anime: "✦", moderation: "✓" };
        const activityList = document.getElementById("admin-activity-list");
        if (!data.recent_activity.length) {
            activityList.replaceChildren(Object.assign(document.createElement("p"), { className: "admin-empty", textContent: "No recent activity yet." }));
            return;
        }
        activityList.replaceChildren(...data.recent_activity.map((activity) => {
            const item = document.createElement("div");
            item.className = "admin-activity-item";
            const marker = document.createElement("span");
            marker.className = "admin-activity-icon";
            marker.textContent = icon[activity.kind] || "•";
            const summary = document.createElement("span");
            summary.className = "admin-activity-copy";
            summary.textContent = activity.summary;
            const date = document.createElement("time");
            date.className = "admin-activity-date";
            date.textContent = escapeDate(activity.at);
            item.append(marker, summary, date);
            return item;
        }));
    }

    async function loadAnime() {
        const params = new URLSearchParams({ page: String(currentPage), limit: String(pageSize) });
        if (searchInput.value.trim()) params.set("q", searchInput.value.trim());
        const data = await api.request(`/admin/anime?${params}`);
        totalItems = data.total;
        const rows = data.items.map((anime) => {
            const title = cell(subline(anime.title, anime.description), "admin-title-cell");
            const source = document.createElement("div");
            source.append(pill(anime.source_type, anime.source_type === "AniList" ? "" : "is-muted"));
            if (anime.locally_edited) source.append(document.createTextNode(" "), pill("Edited", "is-warning"));
            const actions = document.createElement("div");
            actions.className = "admin-row-actions";
            actions.append(
                actionButton("Edit", () => openEditor(anime)),
                actionButton("Delete", () => deleteAnime(anime), true),
            );
            return row([title, anime.genre, anime.studio || "—", source, actions]);
        });
        setTable(["Title", "Genres", "Studio", "Origin", "Actions"], rows, "No anime titles match this search.");
        updatePagination(data.total);
    }

    async function loadUsers() {
        const params = new URLSearchParams({ page: String(currentPage), limit: String(pageSize) });
        if (searchInput.value.trim()) params.set("q", searchInput.value.trim());
        const data = await api.request(`/admin/users?${params}`);
        totalItems = data.total;
        const rows = data.items.map((user) => {
            const account = cell(subline(user.name, user.email));
            const status = user.is_active ? pill("Active") : pill("Suspended", "is-warning");
            const joined = escapeDate(user.created_at);
            const actions = document.createElement("div");
            actions.className = "admin-row-actions";
            if (user.is_admin) {
                actions.append(pill("Administrator", "is-muted"));
            } else {
                actions.append(actionButton(user.is_active ? "Suspend" : "Restore", () => changeUserStatus(user), !user.is_active));
            }
            return row([account, status, joined, actions]);
        });
        setTable(["Account", "Status", "Joined", "Actions"], rows, "No accounts match this search.");
        updatePagination(data.total);
    }

    async function loadComments() {
        const data = await api.request(`/admin/comments?page=${currentPage}&limit=${pageSize}`);
        totalItems = data.total;
        const rows = data.items.map((comment) => {
            const content = cell(subline(comment.comment, `${comment.user_name} · ${escapeDate(comment.created_at)}`));
            const title = cell(subline(comment.anime_title, comment.is_spoiler ? "Spoiler-marked comment" : ""));
            const actions = document.createElement("div");
            actions.className = "admin-row-actions";
            actions.append(
                actionButton("Approve", () => reviewComment(comment)),
                actionButton("Delete", () => deleteComment(comment), true),
            );
            return row([content, title, actions]);
        });
        setTable(["Comment", "On anime", "Actions"], rows, "The moderation queue is clear.");
        updatePagination(data.total);
    }

    async function loadAudit() {
        const entries = await api.request("/admin/audit?limit=100");
        totalItems = entries.length;
        const start = (currentPage - 1) * pageSize;
        const rows = entries.slice(start, start + pageSize).map((entry) => {
            const actor = cell(subline(entry.actor_name, entry.actor_email));
            const target = cell(`${entry.target_type} #${entry.target_id ?? "—"}`);
            const details = entry.details && entry.details.title ? ` · ${entry.details.title}` : "";
            return row([escapeDate(entry.created_at), actor, entry.action.replaceAll("_", " "), target, details || "—"]);
        });
        setTable(["When", "Administrator", "Action", "Target", "Details"], rows, "No moderation actions have been recorded yet.");
        updatePagination(entries.length);
    }

    function updatePagination(total) {
        const pages = Math.max(1, Math.ceil(total / pageSize));
        document.getElementById("admin-page-label").textContent = `${total ? (currentPage - 1) * pageSize + 1 : 0}–${Math.min(currentPage * pageSize, total)} of ${total}`;
        document.getElementById("admin-page-prev").disabled = currentPage <= 1;
        document.getElementById("admin-page-next").disabled = currentPage >= pages;
    }

    async function loadTab() {
        tableBody.replaceChildren(row([cell("Loading administration data…", "admin-empty")]));
        const loaders = { anime: loadAnime, users: loadUsers, comments: loadComments, audit: loadAudit };
        try {
            await loaders[activeTab]();
        } catch (error) {
            showFeedback(error.message || "Could not load administration data.", true);
            setTable(["Status"], [], "The administration request failed. Please try again.");
            totalItems = 0;
            updatePagination(totalItems);
        }
        document.getElementById("admin-create-anime").hidden = activeTab !== "anime";
        searchInput.hidden = !["anime", "users"].includes(activeTab);
    }

    function openEditor(anime) {
        form.reset();
        form.elements.anime_id.value = anime ? anime.id : "";
        document.getElementById("anime-dialog-title").textContent = anime ? "Edit anime" : "Add an anime";
        document.getElementById("anime-save-button").textContent = anime ? "Save changes" : "Add title";
        for (const field of ["title", "genre", "rating", "episode", "studio", "description", "released_date", "cover_image", "source_url"]) {
            if (anime && anime[field] != null) form.elements[field].value = anime[field];
        }
        dialog.showModal();
    }

    async function saveAnime(event) {
        event.preventDefault();
        const formData = new FormData(form);
        const id = formData.get("anime_id");
        const payload = {};
        for (const field of ["title", "genre", "studio", "description", "released_date", "cover_image", "source_url"]) {
            const value = String(formData.get(field) || "").trim();
            if (value) payload[field] = value;
            else if (["studio", "released_date", "cover_image", "source_url"].includes(field)) payload[field] = null;
        }
        for (const field of ["rating", "episode"]) {
            const value = String(formData.get(field) || "").trim();
            if (value) payload[field] = Number(value);
            else if (id) payload[field] = null;
        }
        try {
            await api.request(id ? `/admin/anime/${encodeURIComponent(id)}` : "/admin/anime", {
                method: id ? "PATCH" : "POST",
                body: JSON.stringify(payload),
            });
            dialog.close();
            showFeedback(id ? "Anime changes saved. Local edits are now marked." : "Anime added to the catalog.", false);
            await Promise.all([loadAnime(), loadOverview()]);
        } catch (error) {
            const duplicateHint = Number.isInteger(error.existingId) ? ` Existing entry: #${error.existingId}.` : "";
            showFeedback(`${error.message || "Could not save this title."}${duplicateHint}`, true);
        }
    }

    async function deleteAnime(anime) {
        if (!window.confirm(`Delete "${anime.title}" and its associated comments and watchlist entries? This cannot be undone.`)) return;
        try {
            await api.request(`/admin/anime/${anime.id}`, { method: "DELETE" });
            showFeedback(`${anime.title} was deleted.`, false);
            await Promise.all([loadAnime(), loadOverview()]);
        } catch (error) {
            showFeedback(error.message || "Could not delete this title.", true);
        }
    }

    async function changeUserStatus(user) {
        const shouldSuspend = user.is_active;
        let reason = "";
        if (shouldSuspend) {
            reason = window.prompt(`Optional suspension reason for ${user.name}:`) || "";
            if (!window.confirm(`Suspend ${user.name}? They will be prevented from using their account.`)) return;
        } else if (!window.confirm(`Restore ${user.name}'s account?`)) {
            return;
        }
        const params = new URLSearchParams({ is_active: String(!shouldSuspend) });
        if (reason.trim()) params.set("reason", reason.trim());
        try {
            await api.request(`/admin/users/${user.id}/status?${params}`, { method: "PATCH" });
            showFeedback(shouldSuspend ? `${user.name} was suspended.` : `${user.name} was restored.`, false);
            await Promise.all([loadUsers(), loadOverview()]);
        } catch (error) {
            showFeedback(error.message || "Could not update this account.", true);
        }
    }

    async function reviewComment(comment) {
        try {
            await api.request(`/admin/comments/${comment.id}/review`, { method: "POST" });
            showFeedback("Comment reviewed and approved.", false);
            await Promise.all([loadComments(), loadOverview()]);
        } catch (error) {
            showFeedback(error.message || "Could not review this comment.", true);
        }
    }

    async function deleteComment(comment) {
        if (!window.confirm(`Remove this comment by ${comment.user_name}? The action will be recorded.`)) return;
        try {
            await api.request(`/admin/comments/${comment.id}`, { method: "DELETE" });
            showFeedback("Comment removed and moderation action recorded.", false);
            await Promise.all([loadComments(), loadOverview()]);
        } catch (error) {
            showFeedback(error.message || "Could not remove this comment.", true);
        }
    }

    async function start() {
        if (!api.getToken()) {
            window.location.replace("/login.html");
            return;
        }
        try {
            const user = await api.request("/auth/me");
            if (!user.is_admin) {
                showFeedback("This account does not have administrator access.", true);
                document.getElementById("admin-last-updated").textContent = "Access denied";
                return;
            }
            await Promise.all([loadOverview(), loadTab()]);
        } catch (error) {
            if (error.status === 401) api.clearToken();
            showFeedback(error.message || "Administrator sign-in is required.", true);
            document.getElementById("admin-last-updated").textContent = "Access denied";
        }
    }

    document.querySelectorAll("[data-admin-tab]").forEach((button) => {
        button.addEventListener("click", () => {
            activeTab = button.dataset.adminTab;
            currentPage = 1;
            document.querySelectorAll("[data-admin-tab]").forEach((tab) => {
                const selected = tab === button;
                tab.classList.toggle("is-active", selected);
                tab.setAttribute("aria-pressed", String(selected));
            });
            loadTab();
        });
    });
    document.getElementById("admin-create-anime").addEventListener("click", () => openEditor(null));
    document.getElementById("anime-dialog-close").addEventListener("click", () => dialog.close());
    document.getElementById("anime-dialog-cancel").addEventListener("click", () => dialog.close());
    form.addEventListener("submit", saveAnime);
    document.getElementById("refresh-overview").addEventListener("click", async () => {
        try {
            await loadOverview();
            showFeedback("Platform overview refreshed.", false);
        } catch (error) {
            showFeedback(error.message || "Could not refresh the overview.", true);
        }
    });
    document.getElementById("admin-page-prev").addEventListener("click", () => {
        if (currentPage > 1) { currentPage -= 1; loadTab(); }
    });
    document.getElementById("admin-page-next").addEventListener("click", () => {
        if (currentPage * pageSize < totalItems) { currentPage += 1; loadTab(); }
    });
    searchInput.addEventListener("input", () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => { currentPage = 1; loadTab(); }, 250);
    });
    start();
})();
