# Brief: translating the website's own words

The site is arasteh.art, the personal site of Amir Arasteh, a painter and novelist.
His novel *Sedaha* (Persian «صداها», English title *Sounds*), Book One, is free to read in
113 languages; the site also shows his paintings, a guestbook and a support page. The site's
own words are being translated so a visitor sees the whole site in their language.

## Files

- Source: `i18n/source.json` → `strings`: every English string (the key) with `where` (the
  element it sits in, e.g. `h2`, `button@aria-label`, `title`, `js:finder.js`) and `example`
  (a page where it appears, relative to the site root, which you may open to see context).
- Context per language: `i18n/context.json` → the edition's own book title, its "Book One"
  wording, the author's name as the edition writes it, its word for the book's "Opening", a
  line from its Opening, and a sample of how that edition already addresses the reader.
- Output: `i18n/<code>.json` — one JSON object, UTF-8, **every key of `source.json`'s
  `strings` exactly as given**, each mapped to its translation. No other keys.
- Check: `"C:\Program Files\Python311\python.exe" build_i18n.py validate <code>` from the site
  root must print `OK`. Fix and re-run until it does.

## Mechanics (the validator enforces these)

- **Markers** `<0>…</0>`, `<1/>`: inline elements (links, bold). Keep every marker exactly once,
  properly nested. You may move them to where your grammar puts that phrase. Translate the text
  inside `<n>…</n>`. A self-closing `<n/>` is something left as it is (a name, a line break):
  just keep it in a sensible place.
- **`{n}`** is a number filled in later. Keep the same number of `{n}`. Where your language
  inflects a noun by number (Slavic and Baltic languages, Arabic…), choose a wording that
  is correct for any number, e.g. "Reader notes: {n}" instead of "{n} reader notes".
- **`{q}`** is the visitor's own search text. Keep it; you may use your language's quotation marks
  around it.
- Keep leading/trailing punctuation roles: a label ending in ":" stays a label; arrows stay.
  In right-to-left languages (fa, ar) mirror arrows: "→" becomes "←" and "←" becomes "→".

## Names and fixed words

- **Amir Arasteh** (the author): use `author_name` from the context, exactly.
- **Arasteh** alone is the publisher's imprint and logo: always the Latin word `Arasteh`, never
  transliterated (e.g. "Arasteh, home" → your words for "home", with `Arasteh` kept).
- **Sedaha** stays the Latin word `Sedaha` (in fa: `صداها`).
- **Sounds** (the English title) → `book_title`. **Book One** → `book_one`.
  "Sedaha (Sounds)" → "Sedaha (`book_title`)" (fa: just `صداها`). "Sounds, Book One" →
  "`book_title`, `book_one`" in your language's usual order and punctuation.
- **Opening** (the name of the book's first part, e.g. "Picture 2 · Opening") → `opening_word`.
- "… a thread of words that were once sounds…" is a line of the book → use
  `excerpt_from_opening` as given (match its ellipses).
- The site's recurring image is the book's **thread of words** ("Add to the thread", "Your end of
  the thread", "Pick up the thread in", "The thread led nowhere here"). Keep the thread image and
  use the same word for thread that the edition's Opening uses (open `opening_page` and look at
  the Opening text if unsure).
- Unchanged: PayPal, Revolut, Patreon, Buy Me a Coffee, Hamibash, GitHub, arasteh.art, EPUB,
  PDF, ISBN, and e-mail addresses. **Telegram** may take your language's usual spelling.
- Paintings: "Iran I", "Denmark II", "Brazil" → your language's country name, same Roman
  numeral. "The World Through Boteh-Jegheh": translate; Boteh-Jegheh is a name (transliterate
  it in a non-Latin script). "(known as paisley in English)": say how your language knows the
  pattern (e.g. German "Paisley", Persian «بته‌جقه» — for fa drop the parenthesis's English
  framing naturally). "A Yarn-Laden Truck": translate.
- Language names are not in the list on purpose; never add them.

## Voice

- Plain, warm, quiet, literary. No marketing tone, no exclamation marks the English lacks, no
  added words or explanations. Short where the English is short.
- Address the reader the way `register_sample` does (e.g. German *du*, so "Hilf mit"). If the
  sample is formal, be formal everywhere.
- **Navigation tab labels** (Home, Books, Paintings, Guestbook, Support) sit under icons on a
  phone: keep each to one short word if at all possible (about 10 Latin letters at most; 2–4
  characters in Chinese, Japanese, Korean).
- `@aria-label`, `@title`, `@alt` strings are read aloud by screen readers: natural sentences.
- **License texts** (license page, first-edition page): translate faithfully and precisely, in
  a legal register, adding and dropping nothing. The English stays the binding text (the site
  says so separately; do not add that note yourself).
- Guestbook status lines are short system messages: plain and calm.

## Persian (fa)

The site's Persian pages already have Persian navigation words; `context.json` → `fa` →
`required_exact` lists them: use those exact strings for those keys.

## Deliver

Write `i18n/<code>.json` for each of your languages, run the validator until `OK`, and reply with
one line per language: code, OK, and any string you were unsure of (key + your choice + why).
