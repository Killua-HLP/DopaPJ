async function loadAnimeDetail() {
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const animeId = urlParams.get("id");

        console.log("animeId:", animeId);

        const animeDetail = document.getElementById("anime-detail");

        const response = await fetch(`/anime/${animeId}`);

        if (!response.ok) {
            animeDetail.textContent = "No Anime found!";
            return;
        }

        const anime = await response.json();


        const detailInfo = document.createElement("div");
        detailInfo.classList.add("anime-detail-card");

        if (anime.cover_image) {
            const coverImage = document.createElement("img");
            coverImage.classList.add("anime-cover-image", "anime-detail-cover");
            coverImage.src = anime.cover_image;
            coverImage.alt = `${anime.title} cover`;
            coverImage.addEventListener("error", () => coverImage.remove());
            detailInfo.appendChild(coverImage);
        }

        const title = document.createElement("h2");
        title.textContent = anime.title;

        const genre = document.createElement("p");
        genre.textContent = `Genre: ${anime.genre}`;

        const rating = document.createElement("p");
        rating.textContent = `Rating: ${anime.rating}`;

        const episode = document.createElement("p");
        episode.textContent = `Episodes: ${anime.episode}`;

        const description = document.createElement("p");
        description.textContent = `Description: ${anime.description}`;

        const releaseDate = document.createElement("p");
        const dateText = anime.released_date || anime.releaseDate || "N/A";
        releaseDate.textContent = `Release Date: ${dateText}`;

        const backButton = document.createElement("button");
        backButton.textContent = "<== Back to Home";
        backButton.classList.add("back-button");

        backButton.addEventListener("click", function() {
            window.location.href = "/";
        });

        detailInfo.append(
            title,
            genre,
            rating,
            episode,
            description,
            releaseDate,
            backButton
        );

        animeDetail.replaceChildren(detailInfo);

    } catch (error) {
        console.error("Failed to get anime detail:", error);
    }
}

loadAnimeDetail();