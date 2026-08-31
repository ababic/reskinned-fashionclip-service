# Print vision API (`POST /v1/score`)

FashionCLIP scores for product images. Inventory sends image URLs and boolean classifier flags; this service returns ranked scores from **service-owned vocabularies**. **Thresholding, promotion, and attribute writes live in inventory** (`PRINT_VISION_*`), not here.

Machine-readable contract: [`openapi/v1-score.yaml`](../openapi/v1-score.yaml).

`POST /v1/score` also accepts `{"warmup": true}` to load the model without scoring. Throughput-sensitive callers can use `POST /v1/score-batch` (up to 16 items, shared `options`).

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
  "options": {
    "pattern": true,
    "pattern-application": true,
    "colour": true
  }
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `images` | yes | 1–2 objects, each with `url` (`http` or `https`). |
| `options` | yes | Map of classifier slug → boolean. Missing keys are `false`. At least one `true` is required. |

### Options

Every classifier is **opt-in**. `true` runs that pool against the service-owned vocabulary. Omit a key or send `false` → no work, no response key.

Unknown keys → `400 unknown_option`. Non-boolean values → `400 invalid_request`.

| Slug | Aliases | Catalog | Response key |
|------|---------|---------|--------------|
| `pattern-application` | `pattern_application` | 12 warehouse techniques | `scores.pattern-application` |
| `pattern` | — | 49 patterns (warehouse prod plus `Flames`) | `scores.pattern` |
| `embellishment` | — | 7 warehouse embellishments | `scores.embellishment` |
| `lustre` | — | 8 fabric lustre / light effects | `scores.lustre` |
| `appearance` | — | Combined exclusive pool: all four appearance facets above (76 labels) | `scores.appearance` |
| `colour` | `color` | 24 model colour probes | `scores.colour` |
| `subjects` | — | 45 graphic-theme motifs | `scores.subjects` |
| `product-type` | `product_type` | 141 garment types | `scores.product-type` |
| `sleeve-length` | — | sleeve styles | `scores.sleeve-length` |
| `neckline` | — | necklines | `scores.neckline` |
| `trouser-length` | — | trouser lengths | `scores.trouser-length` |
| `skirt-length` | — | skirt lengths | `scores.skirt-length` |
| `dress-length` | — | dress lengths | `scores.dress-length` |
| `shorts-style` | — | shorts silhouettes | `scores.shorts-style` |

Callers do **not** send label lists. Vocabularies are warehouse prod `Attribute.choices` (print / embellishment) or service-owned catalogs (colour, subjects, product-type, style).

Use **`appearance`** when inventory wants one ranked winner across pattern-application, pattern, embellishment, and lustre (warehouse groups these under Appearance). Use the individual flags when you need facet-specific reads — they use different CLIP prompt families because each facet looks different in the image (see below).

Style scores are indicative: use a score/gap floor and avoid persisting a value when the relevant garment area is hidden.

### Appearance prompting

The four appearance facets are **orthogonal** in the warehouse — a garment can be floral *and* placement-print *and* sequinned *and* glossy. CLIP captions therefore use a **different visual question** per facet:

| Facet | What the model is asked | Prompt family |
|-------|-------------------------|---------------|
| `pattern` | What **motif** repeats on the surface? | `a garment with a repeating {motif} pattern on the fabric surface` |
| `pattern-application` | **How/where** is decoration applied? | Coverage and technique — placement vs all-over, woven vs printed, resist-dye, etc. |
| `embellishment` | What is **physically attached** on top? | Raised or sewn-on decoration — beads, sequins, embroidery, fringe |
| `lustre` | How does **light** behave on the fabric? | `the garment's fabric has a {finish} …` — matte, gloss, shimmer, iridescence |

**`appearance`** merges all four vocabularies into one exclusive pool (76 labels). Each label keeps its facet-specific caption, but softmax `p` is across unrelated visual dimensions — use it for single-winner triage, not multi-attribute writes. Prefer individual facet flags when persisting several Appearance attributes on one product.

Known collisions to watch: **Glitter/Sparkly** (lustre) vs **Sequin** (embellishment); **Lace** (pattern-application, fabric construction) vs **Lace trim** (embellishment).

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
          {"value": "Floral", "score": 0.71, "gap": 0.08, "p": 0.62},
          {"value": "Striped", "score": 0.63, "gap": 0.05, "p": 0.28}
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

Only keys for classifiers **enabled** in `options` appear under `scores`.

### Errors

| Status | `error` | When |
|--------|---------|------|
| `400` | `invalid_request` | Malformed JSON, bad URLs, missing/empty `options`, or a non-boolean flag. |
| `400` | `unknown_option` | Unsupported option key. Body includes `accepted` slug list. |
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

Mapped-cosine drop to the **next** label in the **full** pool.

- Large `gap` on the top label → clear winner vs runner-up.
- Near-zero `gap` → tie; do not promote on rank alone.
- Last label in the full pool → `gap: 0`.

Present on **all** lists.

### `p` (exclusive pools only)

Within-pool softmax over exclusive pools: **`appearance`**, **`pattern`**, **`pattern-application`**,
**`embellishment`**, **`lustre`**, **`product-type`**, and all style pools. Answers: “of the
labels in this pool, what share went to the winner?”

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

**Opt-in:** `"subjects": true`. Response: `scores.subjects` — the graphic-theme catalog below. Inventory reads `value` and writes it onto **graphic-theme** when thresholds pass.

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

- Use `"subjects": true`. Unknown keys such as `graphic-theme` return `400 unknown_option`.
- Do not promote `scores.subjects[0]` without `score` + `gap` floors.
- Inferential buckets (Funny, Retro, Politics, Pop culture, Character) often score low.

---

## Product type

**Opt-in:** `"product-type": true` (or `product_type`). Response: `scores.product-type`.

Uses a **fixed garment list** in the service (141 types) — callers do not send the vocabulary unless adding extras. Derived from warehouse ProductType `name_singular` (gendered/age prefixes stripped), then cleaned for CLIP: natural English plurality and title case as `value`; warehouse spellings stay as aliases. Visually distinct types stay (`Jeggings` ≠ `Leggings`, `Casual Shirt` ≠ `Formal Shirt`, `Boot`/`Boots`, `Shoe`/`Shoes`). **Named sets stay**; generic outfit/set catch-alls are omitted. Accessories stay; **homewares, sleeve accessories, pet/nursery niches, and use-case twins of a kept type** (Power / Sports / Swim Leggings → `Leggings`; Starter Bra → `Bra`; Swimming Trunks → `Trunks`) are omitted.

Bag, Basketball Shoes, Beach Top, Beach Trousers, Belt, Bib, Bikini, Bikini Bottom, Bikini Top, Blazer, Blouse, Bodysuit, Boot, Bootie, Boots, Brogues, Boxer Shorts, Bra, Briefs, Camisole, Cape, Cardigan, Casual Shirt, Chelsea Boots, Chukka Boots, Clogs, Coat, Combat Boots, Corset, Court Shoes, Cowboy Boots, Dress, Dressing Gown, Dungarees, Espadrilles, Fleece, Flats, Flip-flops, Formal Shirt, Gilet, Glove, Hat, High Heels, High-Tops, Hiking Boots, Hoodie, Hoodie & Joggers Set, Jacket, Jeans, Jeggings, Joggers, Jumper, Jumpsuit, Kaftan, Knee-High Boots, Knickers, Knitted Vest, Leggings, Long Johns, Loafers, Mary Janes, Mules, Nightie, Onesie, Overshirt, Oxfords, Pants, Playsuit, Plimsolls, Platform Trainers, Polo Shirt, Poncho, Purse, Pyjama Bottom, Pyjama Top, Pyjamas, Romper, Riding Boots, Running Shoes, Sandal, Sarong, Scarf, Shawl & Wrap, Sheepskin Boots, Shoe, Shoes, Shorts, Skirt, Skort, Skate Shoes, Sleepsuit, Slipper, Slip-on Trainers, Snowsuit, Sock, Sports Bra, Sports Jacket, Sports Vest, Stockings, Suit, 2-Piece Suit, Suit Jacket, Suit Skirt, Suit Trousers, Sunglasses, Suspenders, Sweater, Sweater Set, Sweatshirt, Sweatshirt & Joggers Set, Swim Shorts, Swimsuit, T-shirt, Tank, Tankini, Tennis Shoes, Tie, Tights, Top, Top & Bottom Set, Top & Leggings Set, Top & Shorts Set, Top & Skirt Set, Top & Trousers Set, Towel Robe, Tracksuit, Tracksuit Bottom, Tracksuit Top, Trainer, Training Top, Trousers, Trunks, Tuxedo, Vest, Waistcoat, Wallet, Wedges, Wellington Boots, Wetsuit, Wetsuit Bottom, Wetsuit Top.

Each type stores how it appears in English: ``article`` is `"a"`, `"an"`, or `""` (bare plural / mass noun, e.g. Trousers). CLIP captions use that plus an optional spoken form (`2-Piece Suit` → `a photo of a two-piece suit`). The same ``article`` is returned on each `scores.product-type` row so inventory can write “a dress” vs “trousers” without a second table. All types are returned ranked. **`p`** is present (exclusive pool).

---

## Style

Style classification is opt-in and separate from `product-type`. Set the
relevant flags to `true`:

```json
{
  "options": {
    "sleeve-length": true,
    "neckline": true,
    "trouser-length": true,
    "skirt-length": true,
    "dress-length": true,
    "shorts-style": true
  }
}
```

The first five classifiers describe garment construction or length. `trouser-length`
includes `Short`, `Cropped`, `Three-Quarter Length`, `Ankle Length`, and `Full
Length`. `shorts-style`
distinguishes `Cargo Shorts`, `Running Shorts`, `Denim Shorts`, `Tailored
Shorts`, `Chino Shorts`, `Cycling Shorts`, `Basketball Shorts`, `Swim Shorts`,
and `Sweat Shorts`. Every style classifier returns its complete ranked vocabulary
and `p`. These are model signals, not guaranteed attributes: do not persist a
result when the relevant area is cropped, hidden, or tied.

---

## Colour

**The model’s opinion**, not an inventory colour taxonomy. When `"colour": true`
(or `"color": true`), the service probes FashionCLIP’s Farfetch-trained colour
language. Every probe row is returned. Inventory interprets solids vs mixes vs
combinations.

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
    "options": {
      "appearance": true
    }
  }'
```

Or enable individual appearance facets:

```json
{"options": {"pattern-application": true, "pattern": true, "embellishment": true, "lustre": true}}
```

Response includes only enabled classifiers — catalog and style pools are omitted
unless requested.

### Full optional stack

```json
{
  "images": [{"url": "https://cdn.example.com/legging.jpg"}],
  "options": {
    "pattern-application": true,
    "pattern": true,
    "colour": true,
    "subjects": true,
    "product-type": true
  }
}
```

### With colour only

```json
{
  "images": [{"url": "https://cdn.example.com/legging.jpg"}],
  "options": {
    "pattern": true,
    "colour": true
  }
}
```

---

## Boundary with inventory

| This service | Inventory |
|--------------|-----------|
| FashionCLIP scores | `PRINT_VISION_*` thresholds, promotion, writes |
| `subjects` → graphic-theme values | Whether to persist; theme catalog / aliases |
| `colour` probe rows | Whether solid, mix, or combination fits |
| API key at Gateway | `PRINT_VISION_URL`, `PRINT_VISION_API_KEY` |
