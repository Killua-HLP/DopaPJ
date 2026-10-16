const api = window.AnimeHubApi;
const form = document.getElementById("auth-form");
const nameField = document.getElementById("name-field");
const feedback = document.getElementById("auth-feedback");
const switchButton = document.getElementById("auth-switch");
const submitButton = document.getElementById("auth-submit");
const title = document.getElementById("auth-title");
const intro = document.getElementById("auth-intro");
const switchCopy = document.getElementById("switch-copy");
const passwordInput = form.elements.password;
let registering = false;

if (api.getToken()) window.location.replace("/profile.html");

function updateMode() {
    nameField.hidden = !registering;
    form.elements.name.required = registering;
    passwordInput.autocomplete = registering ? "new-password" : "current-password";
    passwordInput.minLength = registering ? 8 : 1;
    title.textContent = registering ? "Make yourself at home." : "Welcome back.";
    intro.textContent = registering
        ? "Join the community, build your watchlist, and share the stories you love."
        : "Sign in to save your favorites, share reviews, and find your next great story.";
    submitButton.textContent = registering ? "Create your account →" : "Sign in →";
    switchCopy.textContent = registering ? "Already have an account?" : "New to Anime Hub?";
    switchButton.textContent = registering ? "Sign in" : "Create an account";
    feedback.textContent = "";
}

switchButton.addEventListener("click", () => {
    registering = !registering;
    updateMode();
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fields = new FormData(form);
    const payload = {
        email: fields.get("email").trim(),
        password: fields.get("password"),
    };
    if (registering) payload.name = fields.get("name").trim();
    submitButton.disabled = true;
    feedback.textContent = registering ? "Creating your account..." : "Signing you in...";
    try {
        const result = await api.request(registering ? "/auth/register" : "/auth/login", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        api.setToken(result.access_token);
        window.location.assign("/profile.html");
    } catch (error) {
        console.error("Authentication failed:", error);
        feedback.textContent = error.message;
    } finally {
        submitButton.disabled = false;
    }
});
