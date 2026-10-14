function debounce(fn, delay = 300) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

async function loadAnime() {
    try {
        const response = await fetch("/anime");

        if (!response.ok) {
            throw new Error("Failed to fetch anime");
        }

        const data = await response.json();
        const container = document.getElementById("anime-container");
        const searchInput = document.getElementById("anime-input");
        const searchButton = document.getElementById("search-button");
        const sortSelect = document.getElementById("sort-select");

        function displayAnime(animeList) {
            container.innerHTML = "";

            if (animeList.length === 0) {
                container.innerHTML = "<h2>No Anime found</h2>";
                return;
            }

            for (let anime of animeList) {
                const animeCard = document.createElement("div");
                animeCard.classList.add("anime-card");

                if (anime.cover_image) {
                    const coverImage = document.createElement("img");
                    coverImage.classList.add("anime-cover-image");
                    coverImage.src = anime.cover_image;
                    coverImage.alt = `${anime.title} cover`;
                    coverImage.loading = "lazy";
                    coverImage.addEventListener("error", () => coverImage.remove());
                    animeCard.appendChild(coverImage);
                }

                const releaseDate = anime.released_date || anime.releaseDate || "N/A";

                animeCard.innerHTML = `
                    <h3>${anime.title}</h3>
                    <p><strong>Genre:</strong> ${anime.genre}</p>
                    <p><strong>Rating:</strong> ⭐ ${anime.rating}</p>
                    <p><strong>Description:</strong> ${anime.description}</p>
                    <p><strong>Release Date:</strong> ${releaseDate}</p>
                    <p><strong>Episodes:</strong> ${anime.episode}</p>
                    <p><strong>Studio:</strong> ${anime.studio}</p>
                    <button class="detail-button">View Details</button>
                `;

                const detailButton = animeCard.querySelector(".detail-button");
                detailButton.addEventListener("click", function () {
                    window.location.href = `/anime-detail.html?id=${anime.id}`;
                });

                container.appendChild(animeCard);
            }
        }

        function filterAndDisplay() {
            const keyword = searchInput ? searchInput.value.toLowerCase().trim() : "";
            const sortBy = sortSelect ? sortSelect.value : "default";

            let result = data.filter(function (anime) {
                const hasMatchingTitle = anime.title.toLowerCase().includes(keyword);
                const hasMatchingGenre = anime.genre.toLowerCase().includes(keyword);

                return hasMatchingTitle || hasMatchingGenre;
            });

            if (sortBy === "name") {
                result.sort((a, b) => a.title.localeCompare(b.title));
            } else if (sortBy === "ratingHigh") {
                result.sort((a, b) => b.rating - a.rating);
            } else if (sortBy === "ratingLow") {
                result.sort((a, b) => a.rating - b.rating);
            }

            displayAnime(result);
        }

        filterAndDisplay();

        if (searchInput) {
            searchInput.addEventListener("input", debounce(filterAndDisplay, 300));
        }

        if (searchButton) {
            searchButton.addEventListener("click", filterAndDisplay);
        }

        if (sortSelect) {
            sortSelect.addEventListener("change", filterAndDisplay);
        }

    } catch (error) {
        console.error("Failed to get anime:", error);
    }
}

loadAnime();