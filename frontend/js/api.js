(function () {
    const TOKEN_KEY = "anime-hub-token";

    function getToken() {
        try {
            return localStorage.getItem(TOKEN_KEY);
        } catch (error) {
            console.error("Browser storage is unavailable:", error);
            return null;
        }
    }

    function setToken(token) {
        try {
            localStorage.setItem(TOKEN_KEY, token);
        } catch (error) {
            console.error("Could not save the sign-in session:", error);
            throw new Error("Your browser could not save the sign-in session. Check its storage settings.");
        }
    }

    function clearToken() {
        try {
            localStorage.removeItem(TOKEN_KEY);
        } catch (error) {
            console.error("Could not clear the sign-in session:", error);
        }
    }

    async function request(path, options) {
        const config = options || {};
        const headers = new Headers(config.headers || {});
        const token = getToken();
        if (token) headers.set("Authorization", `Bearer ${token}`);
        if (config.body && !(config.body instanceof FormData) && !headers.has("Content-Type")) {
            headers.set("Content-Type", "application/json");
        }

        let response;
        try {
            response = await fetch(path, { ...config, headers });
        } catch (error) {
            throw new Error("Could not reach Anime Hub. Check your connection and try again.");
        }

        if (response.status === 204) return null;
        const contentType = response.headers.get("content-type") || "";
        const payload = contentType.includes("application/json") ? await response.json() : null;
        if (!response.ok) {
            const serverDetail = payload && payload.detail;
            const detail = typeof serverDetail === "string"
                ? serverDetail
                : serverDetail && typeof serverDetail.message === "string"
                    ? serverDetail.message
                    : `Request failed (${response.status}).`;
            const failure = new Error(detail);
            failure.status = response.status;
            if (serverDetail && Number.isInteger(serverDetail.existing_id)) {
                failure.existingId = serverDetail.existing_id;
            }
            throw failure;
        }
        return payload;
    }

    window.AnimeHubApi = { TOKEN_KEY, getToken, setToken, clearToken, request };
})();
