# Kod-Vit

No1
här är en annan text.

## Uppdatera hemsidan

Sidan är statisk och ligger i rotmappen:

- `index.html` — innehåll och sektioner
- `style.css` / `main.js` — design och interaktion
- `assets/` — hero, omslag, ikoner

Gömda sektioner (Video, Spelningar, Merch, Nyhetsbrev, Kontakt, Facebook) ligger som HTML-kommentarer i `index.html` och kan slås på när riktigt innehåll finns.

För att hämta om riktiga Spotify-omslag saknas eller behöver uppdateras:

```bash
pip install pillow requests
python scripts/fetch-covers.py
```

Committa ändringarna till `main` så uppdateras den publicerade sidan automatiskt när GitHub Pages är påslaget.

## Publicera med GitHub Pages

1. Öppna repot på GitHub.
2. Gå till **Settings → Pages**.
3. Under **Build and deployment**, välj **Deploy from a branch**.
4. Välj branch **main** och mapp **/ (root)**.
5. Spara. Sidan blir tillgänglig på `https://<användarnamn>.github.io/<repo-namn>/` (eller egen domän om du kopplar en).
