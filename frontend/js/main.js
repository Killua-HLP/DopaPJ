(async function () {
    const api = window.AnimeHubApi;
    const authArea = document.getElementById("auth-area");
    if (!api || !authArea) return;

    if (!api.getToken()) {
        authArea.hidden = false;
        return;
    }

    try {
        const user = await api.request("/auth/me");
        const profileLink = document.createElement("a");
        profileLink.className = "account-link";
        profileLink.href = "/profile.html";
        profileLink.textContent = user.name;
        profileLink.setAttribute("aria-label", `Open ${user.name}'s profile`);
        const accountLinks = [profileLink];
        if (user.is_admin) {
            const adminLink = document.createElement("a");
            adminLink.className = "account-link";
            adminLink.href = "/admin.html";
            adminLink.textContent = "Admin";
            accountLinks.push(adminLink);
        }

        const signOut = document.createElement("button");
        signOut.className = "sign-out-button";
        signOut.type = "button";
        signOut.textContent = "Sign out";
        signOut.addEventListener("click", () => {
            api.clearToken();
            window.location.assign("/");
        });
        authArea.replaceChildren(...accountLinks, signOut);
        authArea.hidden = false;
    } catch (error) {
        console.error("Could not load the signed-in account:", error);
        if (error.status === 401) api.clearToken();
        authArea.hidden = false;
    }
})();
