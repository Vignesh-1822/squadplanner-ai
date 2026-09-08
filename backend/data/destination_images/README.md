# Manually added destination photos

Most destination photography resolves automatically from Wikipedia (467 of 480, ~97%). The
places below have no usable image there — either the article has no lead photo, or the place is
a region Wikipedia covers under a different title. Automatic search was tried and rejected: it
returned *Pope John VI* for "St. John" and a UFO-abduction article for "White Mountains", which
is worse than showing nothing.

Anything without a photo falls back to a colour gradient keyed to the destination type, so the
cards still look deliberate. Adding a photo here is optional polish.

## How to add one

1. Find a photo you have the right to use. Sources that are safe commercially:
   [Unsplash](https://unsplash.com), [Pexels](https://pexels.com),
   [Wikimedia Commons](https://commons.wikimedia.org), or your own photograph.
2. Save it into this folder named **exactly the destination id**, e.g. `lake_george_ny.jpg`.
   Accepted extensions: `.jpg`, `.jpeg`, `.png`, `.webp`.
3. Landscape, roughly 1200x800 or larger. Cards crop to a 16:9-ish box.
4. Commit the file. Render builds from the repo, so uncommitted images will not deploy.

That is the whole process — no code or config to edit. The backend serves the folder at
`/static/destination-images/` and a file here **overrides** any automatic lookup, so you can
also use it to replace a Wikipedia photo you dislike.

## Crediting (optional)

If a source requires attribution, add an entry to `_credits.json` in this folder:

```json
{
  "lake_george_ny": {
    "credit": "Jane Photographer",
    "source": "unsplash",
    "link": "https://unsplash.com/@janephotographer"
  }
}
```

The credit appears under the photo on the destination detail panel.

## Setup note

`PUBLIC_BASE_URL` in `.env` must be this API's public origin (`http://localhost:8000` locally,
the Render URL in production) — the frontend embeds these URLs directly, so a wrong value gives
broken images.

## Still needed

| Destination | State | Type | Save as | Why it is missing |
|---|---|---|---|---|
| Lake George | NY | town | `lake_george_ny.jpg` | Wikipedia title is a disambiguation page |
| Lake Mead National Recreation Area | NV | natural_area | `lake_mead_nv.jpg` | Article exists but has no lead photo |
| Long Island Wine Country | NY | natural_area | `long_island_wine_country_ny.jpg` | Region; Wikipedia covers it as Long Island AVA |
| Mashantucket | CT | town | `mashantucket_ct.jpg` | Article exists but has no lead photo |
| Naples Beach | FL | beach_town | `naples_fl.jpg` | Region; Wikipedia covers it as Naples, Florida |
| St. Croix | VI | island | `st_croix_vi.jpg` | Article exists but has no lead photo |
| St. John | VI | island | `st_john_vi.jpg` | Ambiguous title; search returns unrelated articles |
| St. Thomas | VI | island | `st_thomas_vi.jpg` | Ambiguous title |
| Tucson Foothills | AZ | resort_town | `tucson_foothills_az.jpg` | Region; Wikipedia covers it as Catalina Foothills |
| Watch Hill | RI | beach_town | `watch_hill_ri.jpg` | Article exists but has no lead photo |
| White Mountains | NH | natural_area | `white_mountains_nh.jpg` | Ambiguous title; search returns unrelated articles |
| Yakima Valley | WA | natural_area | `yakima_valley_wa.jpg` | Region; Wikipedia covers it as Yakima, Washington |
| York Beach | ME | beach_town | `york_beach_me.jpg` | Region; Wikipedia covers it under York, Maine |

_13 of 480 destinations. Regenerate this list after adding photos._
