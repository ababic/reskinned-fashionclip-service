# Print vision API (`POST /v1/score`)

FashionCLIP scores for product images. Inventory sends image URLs and label pools; this service returns ranked scores only. **Thresholding, promotion, and attribute writes live in inventory** (`PRINT_VISION_*`), not here.

Machine-readable contract: [`openapi/v1-score.yaml`](../openapi/v1-score.yaml).

`POST /v1/score` also accepts `{"warmup": true}` to load the model without scoring. Throughput-sensitive callers can use `POST /v1/score-batch` (up to 16 items, shared `pools`).

## Authentication

| Header | Value |
|--------|--------|
| `content-type` | `application/json` |
| `x-api-key` | `PRINT_VISION_API_KEY` (API Gateway key) |

Base URL is environment-specific (`PRINT_VISION_URL` in inventory).

## Request

```json
{
  "images": [{"url": "https://cdn.example.com/garment.jpg"}],
  "pools": {
    "pattern-application": ["Placement print", "All-over print"],
    "pattern": ["Floral", "Striped", "Plain"],
    "colour": []
  },
  "top_k": 3
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `images` | yes | 1–2 objects, each with `url` (`http` or `https`). |
| `pools` | yes | Non-empty map of pool slug → label list. See [Pools](#pools). |
| `top_k` | no | Default `3`, max `5`. Applies to **print** pools only (`pattern`, `pattern-application`). |

### Pools

Every classification is **opt-in**: only slugs present in `pools` are scored. Omit a slug → no work, no response key.

Closed taxonomy. Unknown slugs → `400 unknown_taxonomy`.

| Slug | Aliases | Request | `top_k` | Response key |
|------|---------|---------|---------|--------------|
| `pattern-application` | `pattern_application` | label list (required) | yes | `scores.pattern-application` |
| `pattern` | — | label list (required) | yes | `scores.pattern` |
| `colour` | `color` | `[]` or extras | **ignored** | `scores.colour` |
| `subjects` | — | `[]` only | **ignored** | `scores.subjects` |
| `product-type` | `product_type` | `[]` or extras | **ignored** | `scores.product-type` |
| `sleeve-length` | — | `[]` only | **ignored** | `scores.sleeve-length` |
| `neckline` | — | `[]` only | **ignored** | `scores.neckline` |
| `trouser-length` | — | `[]` only | **ignored** | `scores.trouser-length` |
| `skirt-length` | — | `[]` only | **ignored** | `scores.skirt-length` |
| `dress-length` | — | `[]` only | **ignored** | `scores.dress-length` |
| `shorts-style` | — | `[]` only | **ignored** | `scores.shorts-style` |

**Legacy:** `graphic-theme` / `graphic_theme` is ignored (no `400`). Use `subjects: []` instead.

**Print pools** — caller sends the label list (inventory’s candidate values). Known labels get tailored captions; unknown labels use the taxonomy fallback.

**Catalog pools** — `colour`, `subjects`, and `product-type` use **service-owned vocabularies**. Empty `[]` is enough. Optional extra strings are merged in for `colour` and `product-type` only (not `subjects`).

**Style pools** — `sleeve-length`, `neckline`, `trouser-length`, `skirt-length`,
`dress-length`, and `shorts-style` use fixed service-owned vocabularies. Empty
`[]` is enough. They return all ranked candidates and use `p` because each pool
represents one primary choice. Style scores are indicative: use a score/gap
floor and avoid persisting a value when the relevant garment area is hidden.

## Response

### Success (`200`)

At least one image scored. Per-image failures appear in `errors` without failing the whole batch.

```json
{
  "results": [
    {
      "image_index": 0,
      "url": "https://cdn.example.com/garment.jpg",
      "scores": {
        "pattern": [
          {"value": "Plain", "score": 0.71, "gap": 0.08, "p": 0.62},
          {"value": "Floral", "score": 0.63, "gap": 0.05, "p": 0.28}
        ],
        "colour": [
          {"value": "Black", "score": 0.68, "gap": 0.04, "kind": "solid"},
          {"value": "Grey mix", "score": 0.61, "gap": 0.02, "kind": "mix"},
          {"value": "Navy, Black and Grey", "score": 0.55, "gap": 0.0, "kind": "combination"}
        ],
        "subjects": [
          {"value": "Safari", "score": 0.42, "gap": 0.01},
          {"value": "Wildlife", "score": 0.41, "gap": 0.0}
        ],
        "product-type": [
          {"value": "Leggings", "score": 0.74, "gap": 0.06, "p": 0.58, "article": ""}
        ]
      }
    }
  ],
  "errors": []
}
```

Only keys for pools **requested** appear under `scores`.

### Errors

| Status | `error` | When |
|--------|---------|------|
| `400` | `invalid_request` | Malformed JSON, bad URLs, empty pools after parsing, invalid `top_k`. |
| `400` | `unknown_taxonomy` | Unsupported pool slug. Body includes `accepted` slug list. |
| `422` | `all_images_failed` | Every image failed (`results` empty, `errors` populated). |

Per-image `errors[]` entries:

| `error` | Meaning |
|---------|---------|
| `image_unavailable` | Fetch/decode failed (timeout, HTTP error, not an image). `detail` e.g. `timeout fetching image`, `http_404`. |
| `scoring_failed` | Unexpected scorer failure. |

---

## Scoring fields

Every ranked row includes **`value`** and **`score`**. Optional fields depend on pool type.

### `score`

Mapped cosine similarity in **`[0, 1]`**. Same scale as before aspect-specific captions — existing `PRINT_VISION_*` thresholds on `score` still apply.

Absolute values sit in a narrow band (many garments cluster around the middle). **Use rank and `gap`, not `score` alone, as a confidence proxy.**

### `gap`

Mapped-cosine drop to the **next** label in the **full** pool, computed **before** `top_k` truncation.

- Large `gap` on the top label → clear winner vs runner-up (including labels omitted from the response).
- Near-zero `gap` → tie; do not promote on rank alone.
- Last label in the full pool → `gap: 0`.

Present on **all** lists: request pools, `colour`, and `subjects`.

### `p` (exclusive pools only)

Within-pool softmax over exclusive pools: **`pattern`**, **`pattern-application`**,
**`product-type`**, and all style pools. Answers: “of the labels in this pool,
what share went to the winner?”

- **Not** a calibrated world probability.
- **Not** comparable across different label lists or pools.
- **Absent** on `colour` and `subjects` (multi-label; several themes can apply).

Use `p` only when the request vocabulary is stable (same labels every time).

### Recommended promotion check (inventory)

```
top label wins
AND score >= PRINT_VISION_THRESHOLD
AND gap >= PRINT_VISION_GAP_FLOOR
AND (optional, exclusive pools) p >= PRINT_VISION_P_FLOOR
```

---

## Subjects (graphic-theme)

**Opt-in:** include `"subjects": []` in `pools`. Response: `scores.subjects` — the graphic-theme catalog below. Inventory reads `value` and writes it onto **graphic-theme** when thresholds pass.

Captions name **visual synonyms** (lion, mermaid, anchor) and **exclude neighbouring buckets** (e.g. Ocean ≠ Nautical, Safari ≠ animal print). Leopard / tiger / zebra are **not** subjects — use **`pattern`** for animal print.

### Inventory catalog (34)

These match live style-hint / `graphic-theme` values:

| Value | Visual focus (caption gist) |
|-------|----------------------------|
| Brand logo | logo, wordmark |
| Character | character, mascot |
| Dinosaurs | dinosaur, t-rex |
| Dragons | dragon |
| Fairy tale | princess, fairy, castle — not knight/soldier |
| Farm | cow, pig, chicken, sheep, tractor — not horse/unicorn |
| Food | burger, pizza, coffee, cocktail, dessert |
| Funny | humorous, joke, novelty |
| Gothic | skull, skeleton, vampire — not halloween/angel |
| Heart | heart |
| Horses | horse, pony — not unicorn/farm |
| Insects | bee, butterfly, ladybird, dragonfly |
| Medieval | knight, king, soldier, armour — not princess/castle |
| Mermaids | mermaid — not anchor/fish |
| Music | guitar, piano, vinyl, musical notes, band |
| Nautical | anchor, sailboat, lighthouse, compass, ship's wheel — not mermaid/fish |
| Ocean | fish, whale, shark, turtle, dolphin, octopus, seahorse — not anchor/mermaid |
| Pets | dog, cat, rabbit — not animal print |
| Politics | political, protest — not slogan-only |
| Pop culture | movie, television, comic |
| Religious | angel, demon, cross, saint — not christmas/halloween |
| Reptiles | snake, lizard, crocodile — not snake print |
| Retro | retro, vintage graphic |
| Romance | rose, kiss — not heart |
| Safari | lion, monkey, elephant — not animal print |
| Scenic | landscape, mountain, beach scene |
| Seasonal | christmas, easter, halloween, snowflake, festive — not cross/angel |
| Space | rocket, planet, astronaut, galaxy, alien, UFO |
| Sport | football, rugby, cricket, basketball, tennis, skateboard, racing |
| Star | star |
| Travel | map, city, landmark |
| Unicorns | unicorn — not horse |
| Vehicles | car, motorcycle, airplane, train, truck |
| Warriors | samurai, ronin, ninja — not knight/comic |

### Service extensions (11)

Common on garments but **not** in the live hint catalog yet. Returned in `subjects`; inventory should only **persist** them after adding the same names to graphic-theme / aliases:

Birds, Cards, Celestial, Flame, Fruit, Lips, Mushroom, Peace, Rainbow, Tropical, Wildlife.

### Caller notes

- Use `"subjects": []`, not `graphic-theme`.
- Do not promote `scores.subjects[0]` without `score` + `gap` floors.
- Inferential buckets (Funny, Retro, Politics, Pop culture, Character) often score low.

---

## Product type

**Opt-in:** include `"product-type": []` (or `product_type`). Response: `scores.product-type`.

Uses a **fixed garment list** in the service (141 types) — callers do not send the vocabulary unless adding extras. Derived from warehouse ProductType `name_singular` (gendered/age prefixes stripped), then cleaned for CLIP: natural English plurality and title case as `value`; warehouse spellings stay as aliases. Visually distinct types stay (`Jeggings` ≠ `Leggings`, `Casual Shirt` ≠ `Formal Shirt`, `Boot`/`Boots`, `Shoe`/`Shoes`). **Named sets stay**; generic outfit/set catch-alls are omitted. Accessories stay; **homewares, sleeve accessories, pet/nursery niches, and use-case twins of a kept type** (Power / Sports / Swim Leggings → `Leggings`; Starter Bra → `Bra`; Swimming Trunks → `Trunks`) are omitted.

Bag, Basketball Shoes, Beach Top, Beach Trousers, Belt, Bib, Bikini, Bikini Bottom, Bikini Top, Blazer, Blouse, Bodysuit, Boot, Bootie, Boots, Brogues, Boxer Shorts, Bra, Briefs, Camisole, Cape, Cardigan, Casual Shirt, Chelsea Boots, Chukka Boots, Clogs, Coat, Combat Boots, Corset, Court Shoes, Cowboy Boots, Dress, Dressing Gown, Dungarees, Espadrilles, Fleece, Flats, Flip-flops, Formal Shirt, Gilet, Glove, Hat, High Heels, High-Tops, Hiking Boots, Hoodie, Hoodie & Joggers Set, Jacket, Jeans, Jeggings, Joggers, Jumper, Jumpsuit, Kaftan, Knee-High Boots, Knickers, Knitted Vest, Leggings, Long Johns, Loafers, Mary Janes, Mules, Nightie, Onesie, Overshirt, Oxfords, Pants, Playsuit, Plimsolls, Platform Trainers, Polo Shirt, Poncho, Purse, Pyjama Bottom, Pyjama Top, Pyjamas, Romper, Riding Boots, Running Shoes, Sandal, Sarong, Scarf, Shawl & Wrap, Sheepskin Boots, Shoe, Shoes, Shorts, Skirt, Skort, Skate Shoes, Sleepsuit, Slipper, Slip-on Trainers, Snowsuit, Sock, Sports Bra, Sports Jacket, Sports Vest, Stockings, Suit, 2-Piece Suit, Suit Jacket, Suit Skirt, Suit Trousers, Sunglasses, Suspenders, Sweater, Sweater Set, Sweatshirt, Sweatshirt & Joggers Set, Swim Shorts, Swimsuit, T-shirt, Tank, Tankini, Tennis Shoes, Tie, Tights, Top, Top & Bottom Set, Top & Leggings Set, Top & Shorts Set, Top & Skirt Set, Top & Trousers Set, Towel Robe, Tracksuit, Tracksuit Bottom, Tracksuit Top, Trainer, Training Top, Trousers, Trunks, Tuxedo, Vest, Waistcoat, Wallet, Wedges, Wellington Boots, Wetsuit, Wetsuit Bottom, Wetsuit Top.

Each type stores how it appears in English: ``article`` is `"a"`, `"an"`, or `""` (bare plural / mass noun, e.g. Trousers). CLIP captions use that plus an optional spoken form (`2-Piece Suit` → `a photo of a two-piece suit`). The same ``article`` is returned on each `scores.product-type` row so inventory can write “a dress” vs “trousers” without a second table. Extra caller labels (e.g. `"Kimono"`) infer a determiner; warehouse singulars (`Beach Trouser`) map to the plural row. **`top_k` is ignored** — all types are returned ranked. **`p`** is present (exclusive pool).

---

## Style

Style classification is opt-in and separate from `product-type`. Include an
empty pool to request the service-owned vocabulary:

```json
{
  "sleeve-length": [],
  "neckline": [],
  "trouser-length": [],
  "skirt-length": [],
  "dress-length": [],
  "shorts-style": []
}
```

The first five pools describe garment construction or length. `trouser-length`
includes `Short`, `Cropped`, `Three-Quarter Length`, `Ankle Length`, and `Full
Length`. `shorts-style`
distinguishes `Cargo Shorts`, `Running Shorts`, `Denim Shorts`, `Tailored
Shorts`, `Chino Shorts`, `Cycling Shorts`, `Basketball Shorts`, `Swim Shorts`,
and `Sweat Shorts`. Every style pool returns its complete ranked vocabulary;
`top_k` is ignored and `p` is attached. These are model signals, not
guaranteed attributes: do not persist a result when the relevant area is
cropped, hidden, or tied.

---

## Colour

**The model’s opinion**, not an inventory colour taxonomy. When `colour` (or `color`) is present in `pools`, the service probes FashionCLIP’s Farfetch-trained colour language. **`top_k` is ignored** — every probe row is returned. Inventory interprets solids vs mixes vs combinations.

### Request

```json
"colour": []
```

An empty list is enough. Extra strings are merged into the probe (e.g. `"colour": ["Chartreuse"]` adds Chartreuse solid + mix).

### Built-in vocabulary (24)

Black, White, Cream, Beige, Brown, Grey, Charcoal, Navy, Blue, Light blue, Teal, Red, Burgundy, Pink, Green, Olive, Khaki, Yellow, Orange, Purple, Lilac, Gold, Silver, Multi.

### Three `kind` values

| `kind` | `value` example | Caption shape |
|--------|-----------------|---------------|
| `solid` | `Grey` | `a garment that is grey in colour` |
| `mix` | `Grey mix` | `a multicolour garment with grey hues` |
| `combination` | `Navy, Black and Grey` | `a garment featuring navy, black and grey` |

**Probe order**

1. Every built-in colour (plus caller extras) as **solid** and **mix**, except **Multi** (solid only: `a multicolour garment`).
2. Take the **top 3 solids** (excluding Multi).
3. Score **one** named **combination** from those three (exactly 3 colours; no 2- or 4-way combos).

### Caller interpretation

- Compare **solid** vs **mix** for the same hue (e.g. `Grey` vs `Grey mix`).
- Compare top **solid** vs **combination** when the garment looks multi-coloured.
- Use `gap` between kinds; there is no `p` on colour rows.
- Do not treat `score` as “probability it is navy” — it is relative visual alignment to that caption.

---

## Examples

### Print only (inventory today)

```bash
curl -sS -X POST "$PRINT_VISION_URL" \
  -H "content-type: application/json" \
  -H "x-api-key: $PRINT_VISION_API_KEY" \
  -d '{
    "images": [{"url": "https://cdn.example.com/tee.jpg"}],
    "pools": {
      "pattern-application": ["Placement print", "All-over print"],
      "pattern": ["Floral", "Striped", "Plain"]
    },
    "top_k": 3
  }'
```

Response includes only requested pools — catalog and style pools are omitted
unless asked.

### Full optional stack

```json
{
  "images": [{"url": "https://cdn.example.com/legging.jpg"}],
  "pools": {
    "pattern-application": ["Placement print", "All-over print"],
    "pattern": ["Floral", "Striped", "Plain"],
    "colour": [],
    "subjects": [],
    "product-type": []
  },
  "top_k": 3
}
```

### With colour only

```json
{
  "images": [{"url": "https://cdn.example.com/legging.jpg"}],
  "pools": {
    "pattern": ["Floral", "Striped", "Plain"],
    "colour": []
  },
  "top_k": 2
}
```

### Legacy `graphic-theme` in request (ignored)

```json
{
  "pools": {
    "graphic-theme": ["Safari"],
    "pattern": ["Floral"]
  }
}
```

Accepted; `graphic-theme` is dropped. Use `"subjects": []` instead.

---

## Boundary with inventory

| This service | Inventory |
|--------------|-----------|
| FashionCLIP scores | `PRINT_VISION_*` thresholds, promotion, writes |
| `subjects` → graphic-theme values | Whether to persist; theme catalog / aliases |
| `colour` probe rows | Whether solid, mix, or combination fits |
| API key at Gateway | `PRINT_VISION_URL`, `PRINT_VISION_API_KEY` |
