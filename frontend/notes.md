<h1>        見出し
<p>         文章
<a>         リンク
<img>       画像
<button>    ボタン
<input>     入力欄
<form>      フォーム
<div>       グループ化
<ul> <li>   リスト
h1             → タグ
.anime-title   → class
#detail-button → id

padding → 自分の中に余白を作る
border  → 自分の周りに線を作る
margin  → 自分と他の要素の間に余白を作る

┌─────────────── margin ──────────────┐
│                                     │
│   ┌──────────── border ──────────┐  │
│   │                              │  │
│   │        padding               │  │
│   │      ┌──────────┐            │  │
│   │      │  Content │            │  │
│   │      └──────────┘            │  │
│   │                              │  │
│   └──────────────────────────────┘  │
│                                     │
└─────────────────────────────────────┘

#Method	Meaning	Example	Result

push()	Add to the end	arr.push(4)	[1,2,3,4]
pop()	Remove from the end	arr.pop()	[1,2]
shift()	Remove from the beginning	arr.shift()	[2,3]
unshift()	Add to the beginning	arr.unshift(0)	[0,1,2,3]
map()	Transform every item	arr.map(x => x * 2)	new array
filter()	Keep items matching a condition	arr.filter(x => x > 2)	new array
find()	Find the first matching item	arr.find(x => x > 2)	one item
includes()	Check if an item exists	arr.includes(2)	true/false
indexOf()	Find an item's position	arr.indexOf(2)	index number
forEach()	Run code for every item	arr.forEach(x => console.log(x))	no new array
join()	Combine items into a string	arr.join(", ")	"1, 2, 3"


map() → "Change every item"
const numbers = [1, 2, 3];

const doubled = numbers.map(x => x * 2);
[1, 2, 3]
     ↓ map
[2, 4, 6]
filter() → "Keep some items"
const numbers = [1, 2, 3, 4, 5];

const result = numbers.filter(x => x >= 3);
[1, 2, 3, 4, 5]
      ↓ filter
[3, 4, 5]
find() → "Find ONE"
const numbers = [1, 5, 8, 10];

const result = numbers.find(x => x > 6);

Result:

8

⚠️ find() returns the first matching item.

forEach() → "Do something to every item"
const animeList = ["Naruto", "Nisekoi", "AOT"];

animeList.forEach(function(anime) {
    console.log(anime);
});

Output:

Naruto
Nisekoi
AOT

Unlike map(), forEach() is mainly for doing something, not creating a transformed array.

➕ Adding / Removing
push()

Add to the end:

let anime = ["Naruto", "AOT"];

anime.push("Nisekoi");
["Naruto", "AOT", "Nisekoi"]
pop()

Remove the last:

anime.pop();
unshift()

Add to beginning:

anime.unshift("One Piece");
shift()

Remove from beginning:

anime.shift();

Easy memory:

push()    → add END
pop()     → remove END

unshift() → add START
shift()   → remove START
🔍 Searching
includes()
animeList.includes("Naruto");

Returns:

true

or:

false

Think:

"Does this exist?"

indexOf()
const anime = ["Naruto", "AOT", "Nisekoi"];

anime.indexOf("AOT");

Result:

1

Think:

"Where is it?"

find()
const ratings = [6, 7, 9, 10];

ratings.find(rating => rating >= 8);

Result:

9

Think:

"Give me the first one that matches."

🔤 String Methods You'll Use A LOT

Since you're building a search system, these are important too.

Method	Meaning
.toUpperCase()	Convert to uppercase
.toLowerCase()	Convert to lowercase
.includes()	Check if string contains something
.startsWith()	Check beginning
.endsWith()	Check ending
.trim()	Remove spaces from beginning/end
.split()	Turn string into an array
.join()	Turn array into a string
.replace()	Replace text

Example:

const name = "  Naruto  ";

name.trim();

→ "Naruto"

Very useful for search boxes.

⭐ Super Important Mental Map

Put this in your notes:

ARRAY METHODS

Add / Remove
├── push()     → add END
├── pop()      → remove END
├── unshift()  → add START
└── shift()    → remove START

Process
├── map()      → transform EVERY item
├── filter()   → keep SOME items
├── find()     → find FIRST matching item
└── forEach()  → do something to EVERY item

Search
├── includes() → does it exist?
└── indexOf()  → where is it?

Convert
├── split()    → string → array
└── join()     → array → string
