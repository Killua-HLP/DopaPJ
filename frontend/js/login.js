async function loadAnime() {

    try {
        const response = await fetch("/anime");

        if(!response.ok) {
            throw new Error("Failed to fetch anime");
        }

        const data = await response.json();
        const container = document.getElementById("anime-container");

        const searchInput = document.getElementById("anime-input");
        const searchButton = document.getElementById("search-button")

function displayanime(animelist) {
    for (let anime of animelist) {
            const animeCard = document.createElement("div");
            animeCard.classList.add("anime-card");

            animeCard.innerHTML = `
            <h3>${anime.name}</h3>
            <p><strong>Genre:</strong> ${anime.genre}</p>
            <p><strong>Rating:</strong> ⭐ ${anime.rating}</p>
            `;

            container.appendChild(animeCard);
            displayanime(data)
            }
};

        searchButton.addEventListener("click", function(){
            const keyword = searchInput.value;

            const filteredanime = data.filter(function(anime){
                return anime.name.includes(keyword);
            });
            container.innerHTML = "";

            for (let anime of filteredanime) {
            const animeCard = document.createElement("div");
            animeCard.classList.add("anime-card");

            animeCard.innerHTML = `
            <h3>${anime.name}</h3>
            <p><strong>Genre:</strong> ${anime.genre}</p>
            <p><strong>Rating:</strong> ⭐ ${anime.rating}</p>
            `;

            container.appendChild(animeCard);
            displayanime(filteredanime);
            }

        });  
        
    }
    catch(error) {
        console.log("failed to get anime",error);
    }
}

loadAnime();    

