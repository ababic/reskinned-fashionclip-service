"""Accepted score-pool taxonomies and aspect-specific FashionCLIP captions.

Every classifier is opt-in via boolean flags in the request ``options`` map.
Each enabled pool uses a service-owned vocabulary and tailored CLIP captions.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Taxonomy:
    slug: str
    fallback: str
    captions: dict[str, str] = field(default_factory=dict)
    suggested: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    return_all: bool = False
    exclusive: bool = False


@dataclass(frozen=True)
class ScoreItem:
    value: str
    caption: str
    kind: str | None = None
    article: str | None = None


@dataclass(frozen=True)
class GarmentType:
    """Warehouse product-type leaf plus how it appears in English strings.

    ``article`` is ``"a"``, ``"an"``, or ``""`` (bare plural / mass noun).
    ``spoken`` overrides the CLIP phrase when the display value is awkward
    (``2-Piece Suit`` → ``two-piece suit``). ``aliases`` are warehouse
    singulars / alternate spellings that collapse onto this row.
    """

    value: str
    article: str
    spoken: str | None = None
    aliases: tuple[str, ...] = ()


_COLOUR_COMBINATION_SIZE = 3
_COLOUR_NON_FEATURED = frozenset({"multi", "multicolour", "multicolor"})

MODEL_COLOURS: tuple[str, ...] = (
    "Black",
    "White",
    "Cream",
    "Beige",
    "Brown",
    "Grey",
    "Charcoal",
    "Navy",
    "Blue",
    "Light blue",
    "Teal",
    "Red",
    "Burgundy",
    "Pink",
    "Green",
    "Olive",
    "Khaki",
    "Yellow",
    "Orange",
    "Purple",
    "Lilac",
    "Gold",
    "Silver",
    "Multi",
)

# Warehouse prod Attribute.choices (global, no brand/garment-type overrides).
MODEL_PATTERNS: tuple[str, ...] = (
    "Abstract",
    "Animal print",
    "Ankara",
    "Argyle",
    "Camo",
    "Checked",
    "Cheetah print",
    "Chevron",
    "Colour block",
    "Cow print",
    "Crocodile print",
    "Dalmatian print",
    "Damask",
    "Fair Isle",
    "Flames",
    "Floral",
    "Geometric",
    "Gingham",
    "Giraffe print",
    "Heart print",
    "Herringbone",
    "Houndstooth",
    "Ikat",
    "Kilim",
    "Leaf print",
    "Leopard print",
    "Lynx print",
    "Madras",
    "Mosaic print",
    "Ocelot print",
    "Ombre",
    "Paisley",
    "Pinstripe",
    "Plaid",
    "Polka dot",
    "Puppytooth",
    "Shibori",
    "Slogan",
    "Snake print",
    "Spotted",
    "Spotty",
    "Striped",
    "Stripey",
    "Suzani",
    "Tartan",
    "Tiger print",
    "Toile",
    "Zebra print",
    "Zigzag",
)

MODEL_PATTERN_APPLICATIONS: tuple[str, ...] = (
    "All-over print",
    "Batik",
    "Block print",
    "Border print",
    "Edge print",
    "Jacquard",
    "Knit pattern",
    "Lace",
    "Placement print",
    "Space dye",
    "Tie dye",
    "Wax print",
)

MODEL_LUSTRES: tuple[str, ...] = (
    "Glitter",
    "Glossy",
    "Holographic",
    "Iridescent",
    "Matte",
    "Pearlescent",
    "Shimmer",
    "Sparkly",
)

MODEL_EMBELLISHMENTS: tuple[str, ...] = (
    "Appliquéd",
    "Beaded",
    "Diamante",
    "Embroidered",
    "Fringe",
    "Lace trim",
    "Sequin",
)

# Service-owned style probes. These are deliberately separate from
# ``product-type``: a pair can be ``Shorts`` + ``Running Shorts`` without
# making the style a second garment identity.
STYLE_POOLS: dict[str, tuple[tuple[str, str], ...]] = {
    "sleeve-length": (
        ("Sleeveless", "a garment with no sleeves"),
        ("Cap Sleeve", "a garment with cap sleeves"),
        ("Short Sleeve", "a garment with short sleeves"),
        ("Elbow Sleeve", "a garment with sleeves ending at the elbow"),
        ("Three-Quarter Sleeve", "a garment with three-quarter length sleeves"),
        ("Long Sleeve", "a garment with long sleeves"),
    ),
    "neckline": (
        ("Crew Neck", "a garment with a crew neck"),
        ("V-Neck", "a garment with a V-neck"),
        ("Scoop Neck", "a garment with a scoop neck"),
        ("Square Neck", "a garment with a square neckline"),
        ("Sweetheart Neckline", "a garment with a sweetheart neckline"),
        ("High Neck", "a garment with a high neckline"),
        ("Polo Neck", "a garment with a polo neck"),
        ("Boat Neck", "a garment with a boat neckline"),
        ("Halter Neck", "a garment with a halter neckline"),
        ("Strapless", "a garment with a strapless neckline"),
    ),
    "trouser-length": (
        ("Short", "a pair of short trousers"),
        ("Cropped", "a pair of cropped trousers"),
        ("Three-Quarter Length", "a pair of three-quarter length trousers"),
        ("Ankle Length", "a pair of ankle-length trousers"),
        ("Full Length", "a pair of full-length trousers"),
    ),
    "skirt-length": (
        ("Mini", "a mini skirt"),
        ("Knee Length", "a knee-length skirt"),
        ("Midi", "a midi skirt"),
        ("Maxi", "a maxi skirt"),
    ),
    "dress-length": (
        ("Mini", "a mini dress"),
        ("Knee Length", "a knee-length dress"),
        ("Midi", "a midi dress"),
        ("Maxi", "a maxi dress"),
    ),
    "shorts-style": (
        ("Cargo Shorts", "a pair of cargo shorts"),
        ("Running Shorts", "a pair of running shorts"),
        ("Denim Shorts", "a pair of denim shorts"),
        ("Tailored Shorts", "a pair of tailored shorts"),
        ("Chino Shorts", "a pair of chino shorts"),
        ("Cycling Shorts", "a pair of cycling shorts"),
        ("Basketball Shorts", "a pair of basketball shorts"),
        ("Swim Shorts", "a pair of swim shorts"),
        ("Sweat Shorts", "a pair of sweat shorts"),
    ),
}
STYLE_POOL_SLUGS: tuple[str, ...] = tuple(STYLE_POOLS)

# Warehouse ProductType leaves (prod), cleaned for CLIP scoring:
# - ``value`` is natural English (plural where the noun is always plural;
#   title case). Warehouse spellings stay as aliases.
# - Keep visually distinct types (Jeggings ≠ Leggings; Casual Shirt ≠ Formal
#   Shirt; Boot/Boots and Shoe/Shoes as separate nodes; footwear styles
#   including High Heels, Oxfords, Chelsea / Combat / Cowboy / Knee-High Boots).
# - Keep named sets; drop generic outfit/set catch-alls.
# - Drop homewares, sleeve accessories, pet/nursery niches, and use-case
#   twins of a kept type (Power/Sports/Swim Leggings → Leggings).
GARMENT_TYPES: tuple[GarmentType, ...] = (
    GarmentType("Bag", "a"),
    GarmentType("Basketball Shoes", "", aliases=("Basketball shoe", "Basketball trainers")),
    GarmentType("Beach Top", "a", aliases=("Beach top",)),
    GarmentType("Beach Trousers", "", aliases=("Beach Trouser",)),
    GarmentType("Belt", "a"),
    GarmentType("Bib", "a"),
    GarmentType("Bikini", "a"),
    GarmentType("Bikini Bottom", "a", aliases=("Bikini bottom",)),
    GarmentType("Bikini Top", "a", aliases=("Bikini top",)),
    GarmentType("Blazer", "a"),
    GarmentType("Blouse", "a"),
    GarmentType("Bodysuit", "a"),
    GarmentType("Boot", "a"),
    GarmentType("Bootie", "a"),
    GarmentType("Boots", ""),
    GarmentType("Brogues", "", aliases=("Brogue",)),
    GarmentType("Boxer Shorts", "", aliases=("Boxer short",)),
    GarmentType("Bra", "a", aliases=("Starter Bra",)),
    GarmentType("Briefs", ""),
    GarmentType("Camisole", "a", aliases=("Cami", "Vests & Cami")),
    GarmentType("Cape", "a"),
    GarmentType("Cardigan", "a"),
    GarmentType("Casual Shirt", "a", aliases=("Casual shirt",)),
    GarmentType("Chelsea Boots", "", aliases=("Chelsea boot",)),
    GarmentType("Chukka Boots", "", aliases=("Chukka", "Chukka boot", "Desert boot", "Desert boots")),
    GarmentType("Clogs", "", aliases=("Clog",)),
    GarmentType("Coat", "a"),
    GarmentType("Combat Boots", "", aliases=("Combat boot", "Military boots", "Military boot")),
    GarmentType("Corset", "a"),
    GarmentType("Court Shoes", "", aliases=("Court shoe", "Pumps", "Pump")),
    GarmentType("Cowboy Boots", "", aliases=("Cowboy boot", "Western boots", "Western boot")),
    GarmentType("Dress", "a"),
    GarmentType("Dressing Gown", "a", aliases=("Dressing gown",)),
    GarmentType("Dungarees", ""),
    GarmentType("Espadrilles", "", aliases=("Espadrille",)),
    GarmentType("Fleece", "a"),
    GarmentType("Flats", "", aliases=("Flat", "Ballet flat", "Ballet flats")),
    GarmentType("Flip-flops", "", aliases=("Flip flop", "Flip-flop", "Flip flops")),
    GarmentType("Formal Shirt", "a", aliases=("Formal shirt",)),
    GarmentType("Gilet", "a"),
    GarmentType("Glove", "a"),
    GarmentType("Hat", "a"),
    GarmentType("High Heels", "", aliases=("High heels", "High heals", "Heels")),
    GarmentType("High-Tops", "", aliases=("High-top", "High tops", "High-top trainers", "Hi-tops")),
    GarmentType("Hiking Boots", "", aliases=("Hiking boot", "Walking boot", "Walking boots")),
    GarmentType("Hoodie", "a"),
    GarmentType("Hoodie & Joggers Set", "a", aliases=("Hoodie & joggers set",)),
    GarmentType("Jacket", "a", aliases=("Jackets",)),
    GarmentType("Jeans", ""),
    GarmentType("Jeggings", "", aliases=("Jegging",)),
    GarmentType("Joggers", ""),
    GarmentType("Jumper", "a"),
    GarmentType("Jumpsuit", "a"),
    GarmentType("Kaftan", "a"),
    GarmentType("Knee-High Boots", "", aliases=("Knee high boots", "Knee boots", "Over-the-knee boots")),
    GarmentType("Knickers", ""),
    GarmentType("Knitted Vest", "a"),
    GarmentType(
        "Leggings",
        "",
        aliases=(
            "Power Legging",
            "Power Leggings",
            "Sports Legging",
            "Sports Leggings",
            "Swim legging",
            "Swim Leggings",
        ),
    ),
    GarmentType("Long Johns", "", aliases=("Long john",)),
    GarmentType("Loafers", "", aliases=("Loafer",)),
    GarmentType("Mary Janes", "", aliases=("Mary Jane",)),
    GarmentType("Mules", "", aliases=("Mule",)),
    GarmentType("Nightie", "a", aliases=("Nighty",)),
    GarmentType("Onesie", "a"),
    GarmentType("Overshirt", "an"),
    GarmentType("Oxfords", "", aliases=("Oxford", "Oxford shoes")),
    GarmentType("Pants", "", aliases=("Pant",)),
    GarmentType("Playsuit", "a"),
    GarmentType("Plimsolls", "", aliases=("Plimsoll", "Plimsole", "Plimsoles", "Canvas shoes")),
    GarmentType("Platform Trainers", "", aliases=("Platform trainer", "Platform sneakers", "Chunky trainers")),
    GarmentType("Polo Shirt", "a", aliases=("Polo shirt",)),
    GarmentType("Poncho", "a"),
    GarmentType("Purse", "a"),
    GarmentType("Pyjama Bottom", "a"),
    GarmentType("Pyjama Top", "a"),
    GarmentType("Pyjamas", ""),
    GarmentType("Romper", "a"),
    GarmentType("Riding Boots", "", aliases=("Riding boot", "Equestrian boots")),
    GarmentType("Running Shoes", "", aliases=("Running shoe", "Runners")),
    GarmentType("Sandal", "a"),
    GarmentType("Sarong", "a"),
    GarmentType("Scarf", "a"),
    GarmentType("Shawl & Wrap", "a", aliases=("Shawl & wrap",)),
    GarmentType("Sheepskin Boots", "", aliases=("Sheepskin boot", "Ugg", "Uggs", "Ugg boots")),
    GarmentType("Shoe", "a"),
    GarmentType("Shoes", ""),
    GarmentType("Shorts", ""),
    GarmentType("Skirt", "a"),
    GarmentType("Skort", "a"),
    GarmentType("Skate Shoes", "", aliases=("Skate shoe", "Skate trainers", "Skateboard shoes")),
    GarmentType("Sleepsuit", "a"),
    GarmentType("Slipper", "a"),
    GarmentType("Slip-on Trainers", "", aliases=("Slip-on trainer", "Slip-on sneakers")),
    GarmentType("Snowsuit", "a"),
    GarmentType("Sock", "a"),
    GarmentType("Sports Bra", "a", aliases=("Sports bra",)),
    GarmentType("Sports Jacket", "a"),
    GarmentType("Sports Vest", "a"),
    GarmentType("Stockings", "", aliases=("Stocking",)),
    GarmentType("Suit", "a"),
    GarmentType("2-Piece Suit", "a", "two-piece suit", aliases=("Suit 2 Piece",)),
    GarmentType("Suit Jacket", "a", aliases=("Suit jacket",)),
    GarmentType("Suit Skirt", "a"),
    GarmentType("Suit Trousers", "", aliases=("Suit trouser",)),
    GarmentType("Sunglasses", ""),
    GarmentType("Suspenders", "", aliases=("Suspender",)),
    GarmentType("Sweater", "a"),
    GarmentType("Sweater Set", "a", aliases=("Sweater set",)),
    GarmentType("Sweatshirt", "a"),
    GarmentType("Sweatshirt & Joggers Set", "a", aliases=("Sweatshirt & joggers set",)),
    GarmentType("Swim Shorts", "", aliases=("Swim short",)),
    GarmentType("Swimsuit", "a"),
    GarmentType("T-shirt", "a"),
    GarmentType("Tank", "a"),
    GarmentType("Tankini", "a"),
    GarmentType("Tennis Shoes", "", aliases=("Tennis shoe",)),
    GarmentType("Tie", "a"),
    GarmentType("Tights", ""),
    GarmentType("Top", "a"),
    GarmentType("Top & Bottom Set", "a", aliases=("Top & bottom set",)),
    GarmentType("Top & Leggings Set", "a", aliases=("Top & leggings set",)),
    GarmentType("Top & Shorts Set", "a", aliases=("Top & shorts set",)),
    GarmentType("Top & Skirt Set", "a", aliases=("Top & skirt set",)),
    GarmentType("Top & Trousers Set", "a", aliases=("Top & trousers set",)),
    GarmentType("Towel Robe", "a"),
    GarmentType("Tracksuit", "a"),
    GarmentType("Tracksuit Bottom", "a"),
    GarmentType("Tracksuit Top", "a"),
    GarmentType("Trainer", "a"),
    GarmentType("Training Top", "a", aliases=("Training top",)),
    GarmentType("Trousers", ""),
    GarmentType("Trunks", "", aliases=("Trunk", "Swimming trunk", "Swimming Trunks")),
    GarmentType("Tuxedo", "a"),
    GarmentType("Vest", "a"),
    GarmentType("Waistcoat", "a"),
    GarmentType("Wallet", "a"),
    GarmentType("Wedges", "", aliases=("Wedge",)),
    GarmentType("Wellington Boots", "", aliases=("Wellington boot", "Wellies", "Welly")),
    GarmentType("Wetsuit", "a"),
    GarmentType("Wetsuit Bottom", "a", aliases=("Wetsuit bottom",)),
    GarmentType("Wetsuit Top", "a", aliases=("Wetsuit top",)),
)
MODEL_GARMENT_TYPES: tuple[str, ...] = tuple(item.value for item in GARMENT_TYPES)

# Live inventory graphic-theme catalog (style hint choices + feed aliases).
# ``value`` is the canonical attribute inventory already stores. Captions name
# the visual synonyms FashionCLIP can see and exclude neighbouring buckets.
_INVENTORY_GRAPHIC_SUBJECTS: tuple[tuple[str, str], ...] = (
    ("Brand logo", "the garment features a brand logo or wordmark"),
    ("Character", "the garment features a character or mascot motif"),
    ("Dinosaurs", "the garment features a dinosaur or t-rex motif"),
    ("Dragons", "the garment features a dragon motif"),
    (
        "Fairy tale",
        "the garment features a princess, fairy or castle motif, not a knight or soldier",
    ),
    (
        "Farm",
        "the garment features a cow, pig, chicken, sheep or tractor motif, not a horse or unicorn",
    ),
    ("Food", "the garment features a burger, pizza, coffee, cocktail or dessert motif"),
    ("Funny", "the garment features a humorous joke or novelty motif"),
    (
        "Gothic",
        "the garment features a skull, skeleton or vampire motif, not halloween or an angel",
    ),
    ("Heart", "the garment features a heart motif"),
    (
        "Horses",
        "the garment features a horse or pony motif, not a unicorn or farm animal",
    ),
    ("Insects", "the garment features a bee, butterfly, ladybird or dragonfly motif"),
    (
        "Medieval",
        "the garment features a knight, king, soldier or armour motif, not a princess or castle",
    ),
    ("Mermaids", "the garment features a mermaid motif, not an anchor or fish"),
    ("Music", "the garment features a guitar, piano, vinyl record, musical notes or band motif"),
    (
        "Nautical",
        "the garment features an anchor, sailboat, lighthouse, compass or ship's wheel motif, not a mermaid or fish",
    ),
    (
        "Ocean",
        "the garment features a fish, whale, shark, turtle, dolphin, octopus or seahorse motif, "
        "not an anchor or mermaid",
    ),
    ("Pets", "the garment features a dog, cat or rabbit motif, not an animal print"),
    ("Politics", "the garment features a political or protest motif, not a slogan-only print"),
    ("Pop culture", "the garment features a movie, television or comic motif"),
    (
        "Religious",
        "the garment features an angel, demon, cross or saint motif, not christmas or halloween",
    ),
    (
        "Reptiles",
        "the garment features a snake, lizard or crocodile motif, not a snake print",
    ),
    ("Retro", "the garment features a retro vintage graphic motif"),
    ("Romance", "the garment features a rose or kiss motif, not a heart"),
    (
        "Safari",
        "the garment features a lion, monkey or elephant motif, not an animal print",
    ),
    ("Scenic", "the garment features a landscape, mountain or beach scene motif"),
    (
        "Seasonal",
        "the garment features a christmas, easter, halloween, snowflake or festive motif, not a cross or angel",
    ),
    ("Space", "the garment features a rocket, planet, astronaut, galaxy, alien or UFO motif"),
    (
        "Sport",
        "the garment features a football, rugby, cricket, basketball, tennis, skateboard or racing motif",
    ),
    ("Star", "the garment features a star motif"),
    ("Travel", "the garment features a map, city or landmark motif"),
    ("Unicorns", "the garment features a unicorn motif, not a horse"),
    (
        "Vehicles",
        "the garment features a car, motorcycle, airplane, train or truck motif",
    ),
    (
        "Warriors",
        "the garment features a samurai, ronin or ninja motif, not a knight or comic character",
    ),
)

# Extra visual buckets common on garments but not in the live hint catalog.
# Inventory can persist these only after adding the same names to graphic-theme.
_EXTRA_GRAPHIC_SUBJECTS: tuple[tuple[str, str], ...] = (
    ("Birds", "the garment features an owl, flamingo, swallow or eagle motif, not an insect or safari animal"),
    ("Cards", "the garment features a playing card, dice or poker motif"),
    (
        "Celestial",
        "the garment features a moon, sun, lightning bolt or constellation motif, not a star print or rocket",
    ),
    ("Flame", "the garment features a flame or fire motif"),
    (
        "Fruit",
        "the garment features a strawberry, cherry, watermelon, lemon or pineapple motif, not a burger or dessert",
    ),
    ("Lips", "the garment features a lips motif, not a rose or heart"),
    ("Mushroom", "the garment features a mushroom motif, not food"),
    ("Peace", "the garment features a peace symbol motif"),
    ("Rainbow", "the garment features a rainbow motif"),
    (
        "Tropical",
        "the garment features a palm tree, cactus or monstera motif, not a floral pattern or landscape",
    ),
    (
        "Wildlife",
        "the garment features a wolf, bear, fox or stag motif, not a safari animal, farm animal, pet or animal print",
    ),
)
GRAPHIC_SUBJECTS: tuple[tuple[str, str], ...] = _INVENTORY_GRAPHIC_SUBJECTS + _EXTRA_GRAPHIC_SUBJECTS
GRAPHIC_MOTIFS: tuple[str, ...] = tuple(value for value, _caption in GRAPHIC_SUBJECTS)


def _normalise_label(label: str) -> str:
    return " ".join(label.replace("_", " ").split()).casefold()


_GARMENT_BY_KEY: dict[str, GarmentType] = {
    _normalise_label(name): item for item in GARMENT_TYPES for name in (item.value, *item.aliases)
}


def _captions(entries: dict[str, str]) -> dict[str, str]:
    return {_normalise_label(key): text for key, text in entries.items()}


TAXONOMIES: dict[str, Taxonomy] = {
    "pattern-application": Taxonomy(
        slug="pattern-application",
        aliases=("pattern_application",),
        fallback="a garment whose print or decoration is applied as {label}",
        exclusive=True,
        return_all=True,
        captions=_captions(
            {
                "all-over print": "a garment covered entirely in an all-over repeating print",
                "aop": "a garment covered entirely in an all-over repeating print",
                "all over print": "a garment covered entirely in an all-over repeating print",
                "allover print": "a garment covered entirely in an all-over repeating print",
                "batik": "a garment with a batik wax-resist dye pattern in the fabric",
                "block print": "a garment with a woodblock printed pattern",
                "border print": "a garment with a border print along an edge or hem",
                "edge print": "a garment with a print along a garment edge",
                "jacquard": "a garment with a jacquard pattern woven into the fabric, not a printed design",
                "knit pattern": "a garment with a pattern knitted into the fabric, not a printed design",
                "lace": "a garment made of lace fabric, not lace trim sewn on",
                "placement print": "a garment with a placement print, decoration confined to one area of the garment",
                "printed": "a garment with a placement print, decoration confined to one area of the garment",
                "placement": "a garment with a placement print, decoration confined to one area of the garment",
                "space dye": "a garment with space-dyed yarn and mottled colour, not a printed motif",
                "tie dye": "a garment dyed with a tie-dye resist technique",
                "wax print": "a garment with an African wax-print technique",
            }
        ),
    ),
    "pattern": Taxonomy(
        slug="pattern",
        fallback="a garment with a repeating {label} pattern on the fabric surface",
        exclusive=True,
        return_all=True,
        captions=_captions(
            {
                "abstract": "a garment with an abstract pattern",
                "animal print": "a garment with a generic animal print, not a pictorial animal motif",
                "animal": "a garment with a generic animal print, not a pictorial animal motif",
                "ankara": "a garment with an ankara print pattern",
                "argyle": "a garment with an argyle diamond pattern",
                "camo": "a garment with a camouflage pattern",
                "camouflage": "a garment with a camouflage pattern",
                "checked": "a garment with a checked pattern",
                "check": "a garment with a checked pattern",
                "checkered": "a garment with a checked pattern",
                "cheetah print": "a garment with a cheetah print, not leopard or ocelot print",
                "chevron": "a garment with a chevron zigzag pattern",
                "colour block": "a garment with colour-block panels of solid colour",
                "color block": "a garment with colour-block panels of solid colour",
                "colour-block": "a garment with colour-block panels of solid colour",
                "cow print": "a garment with a cow-hide print, not a pictorial cow motif",
                "crocodile print": "a garment with a crocodile-skin print, not a pictorial reptile motif",
                "dalmatian print": "a garment with a dalmatian spot print, not a pictorial dog motif",
                "damask": "a garment with a damask woven floral pattern",
                "fair isle": "a garment with a fair isle knitted colourwork pattern",
                "flames": "a garment with a repeating flames print pattern, not a single fire motif",
                "flame": "a garment with a repeating flames print pattern, not a single fire motif",
                "flame print": "a garment with a repeating flames print pattern, not a single fire motif",
                "floral": "a garment with a floral pattern",
                "floral print": "a garment with a floral pattern",
                "geometric": "a garment with a geometric pattern",
                "gingham": "a garment with a gingham check pattern",
                "giraffe print": "a garment with a giraffe-skin print, not a pictorial giraffe motif",
                "heart print": "a garment with a repeating heart print pattern, not a single romance motif",
                "herringbone": "a garment with a herringbone pattern",
                "houndstooth": "a garment with a houndstooth pattern",
                "ikat": "a garment with an ikat pattern",
                "kilim": "a garment with a kilim rug geometric pattern",
                "leaf print": "a garment with a repeating leaf print pattern, not a botanical graphic motif",
                "leopard print": "a garment with a leopard print, not cheetah, ocelot or lynx print",
                "leopard": "a garment with a leopard print, not cheetah, ocelot or lynx print",
                "lynx print": "a garment with a lynx print, not leopard or cheetah print",
                "madras": "a garment with a madras check pattern",
                "mosaic print": "a garment with a mosaic tile print",
                "ocelot print": "a garment with an ocelot print, not leopard or cheetah print",
                "ombre": "a garment with an ombre colour gradient",
                "paisley": "a garment with a paisley pattern",
                "pinstripe": "a garment with a pinstripe pattern, not a wide stripe",
                "plaid": "a garment with a plaid pattern",
                "polka dot": "a garment with a regular polka dot pattern",
                "polka dots": "a garment with a regular polka dot pattern",
                "puppytooth": "a garment with a small puppytooth check, not full houndstooth",
                "shibori": "a garment with a shibori resist-dye pattern",
                "slogan": "a garment with a slogan or typography print",
                "snake print": "a garment with a snakeskin print, not a pictorial snake motif",
                "spotted": "a garment with an irregular spotted pattern, not regular polka dots",
                "spotty": "a garment with a casual spotty pattern, not regular polka dots",
                "spot": "a garment with an irregular spotted pattern, not regular polka dots",
                "striped": "a garment with a striped pattern",
                "stripe": "a garment with a striped pattern",
                "stripes": "a garment with a striped pattern",
                "stripey": "a garment with an informal stripey pattern, not a regular pinstripe",
                "suzani": "a garment with a suzani floral embroidery-style pattern",
                "tartan": "a garment with a tartan pattern",
                "tiger print": "a garment with a tiger-stripe print, not a pictorial tiger motif",
                "toile": "a garment with a toile de jouy scenic print",
                "zebra print": "a garment with a zebra-stripe print, not a pictorial zebra motif",
                "zigzag": "a garment with a zigzag pattern, not chevron",
            }
        ),
    ),
    "embellishment": Taxonomy(
        slug="embellishment",
        fallback="a garment with {label} decoration physically attached to the fabric",
        exclusive=True,
        return_all=True,
        captions=_captions(
            {
                "appliquéd": "a garment with fabric appliqué shapes sewn on top of the base material",
                "appliqued": "a garment with fabric appliqué shapes sewn on top of the base material",
                "appliqué": "a garment with fabric appliqué shapes sewn on top of the base material",
                "applique": "a garment with fabric appliqué shapes sewn on top of the base material",
                "beaded": "a garment with visible beads attached to the fabric surface",
                "diamante": "a garment with diamante or rhinestone gems fixed to the surface",
                "embroidered": "a garment with raised stitched embroidery on the fabric, not a printed design",
                "embroidery": "a garment with raised stitched embroidery on the fabric, not a printed design",
                "fringe": "a garment with hanging fringe tassels along an edge",
                "lace trim": "a garment with lace trim edging sewn on, not a garment made wholly of lace",
                "sequin": "a garment covered with attached sequin discs that catch the light",
                "sequins": "a garment covered with attached sequin discs that catch the light",
            }
        ),
    ),
    "lustre": Taxonomy(
        slug="lustre",
        fallback="the garment's fabric has a {label} optical finish under the light",
        exclusive=True,
        return_all=True,
        captions=_captions(
            {
                "glitter": (
                    "the garment's fabric has fine glitter particles embedded in the finish, "
                    "not attached sequins or a glitter print"
                ),
                "glossy": "the garment's fabric has a smooth high-gloss reflective shine across the surface",
                "holographic": "the garment's fabric has a rainbow holographic reflective sheen",
                "iridescent": (
                    "the garment's fabric has a colour-shifting iridescent lustre as the light angle changes"
                ),
                "matte": "the garment's fabric has a flat matte finish that absorbs light without shine",
                "pearlescent": "the garment's fabric has a soft pearlescent inner glow, like a pearl surface",
                "shimmer": (
                    "the garment's fabric has a subtle woven or coated shimmer, without loose glitter particles"
                ),
                "sparkly": (
                    "the garment's fabric has an overall sparkly light-catching finish throughout the material"
                ),
            }
        ),
    ),
    "appearance": Taxonomy(
        slug="appearance",
        fallback="a garment with {label} appearance",
        exclusive=True,
        return_all=True,
    ),
    "colour": Taxonomy(
        slug="colour",
        aliases=("color",),
        fallback="a garment that is {label} in colour",
        return_all=True,
    ),
    "subjects": Taxonomy(
        slug="subjects",
        fallback="the garment features a {label} motif",
        return_all=True,
    ),
    "product-type": Taxonomy(
        slug="product-type",
        aliases=("product_type",),
        fallback="a photo of a {label}",
        exclusive=True,
        return_all=True,
    ),
}
for _style_slug, _style_entries in STYLE_POOLS.items():
    TAXONOMIES[_style_slug] = Taxonomy(
        slug=_style_slug,
        fallback="a garment with {label}",
        return_all=True,
        exclusive=True,
    )

_SLUG_TO_CANONICAL: dict[str, str] = {}
for _taxonomy in TAXONOMIES.values():
    _SLUG_TO_CANONICAL[_taxonomy.slug] = _taxonomy.slug
    for _alias in _taxonomy.aliases:
        _SLUG_TO_CANONICAL[_alias] = _taxonomy.slug

ACCEPTED_SLUGS: tuple[str, ...] = tuple(TAXONOMIES)

# Warehouse ``appearance`` attribute group: one exclusive pool spanning these facets.
APPEARANCE_MEMBER_SLUGS: tuple[str, ...] = (
    "pattern-application",
    "pattern",
    "embellishment",
    "lustre",
)


def resolve_taxonomy(slug: str) -> str | None:
    return _SLUG_TO_CANONICAL.get(slug.strip().casefold())


def _product_type_phrase(label: str) -> tuple[str, str]:
    """Return ``(article, spoken)`` for a product-type label."""
    key = _normalise_label(label)
    known = _GARMENT_BY_KEY.get(key)
    if known is not None:
        return known.article, known.spoken or _normalise_label(known.value)
    if key.endswith("s") and not key.endswith(("ss", "us", "is")):
        return "", key
    if key.startswith("one"):
        return "a", key
    return ("an" if key[:1] in "aeiou" else "a"), key


def _product_type_caption(label: str) -> str:
    """Natural English CLIP prompt from the stored article and spoken form."""
    article, spoken = _product_type_phrase(label)
    if article:
        return f"a photo of {article} {spoken}"
    return f"a photo of {spoken}"


def style_probe_items(pool_slug: str) -> list[ScoreItem]:
    """Return the fixed, exclusive style probes for one optional pool."""
    canonical = resolve_taxonomy(pool_slug)
    if canonical not in STYLE_POOLS:
        raise ValueError(f"unsupported style pool: {pool_slug}")
    return [ScoreItem(value, caption) for value, caption in STYLE_POOLS[canonical]]


def caption_for_label(pool_slug: str, label: str) -> str:
    """Return the CLIP text caption for one label in a known taxonomy."""
    canonical = resolve_taxonomy(pool_slug)
    if canonical is None:
        raise ValueError(f"unsupported taxonomy: {pool_slug}")
    if canonical == "product-type":
        return _product_type_caption(label)
    if canonical in STYLE_POOLS:
        for value, caption in STYLE_POOLS[canonical]:
            if _normalise_label(value) == _normalise_label(label):
                return caption
        return f"a garment with {_normalise_label(label)}"
    taxonomy = TAXONOMIES[canonical]
    key = _normalise_label(label)
    if key in taxonomy.captions:
        return taxonomy.captions[key]
    return taxonomy.fallback.format(label=key)


def returns_full_pool(pool_slug: str) -> bool:
    """Whether this pool returns every scored label (caller interprets the set)."""
    canonical = resolve_taxonomy(pool_slug)
    return canonical is not None and TAXONOMIES[canonical].return_all


def pool_is_exclusive(pool_slug: str) -> bool:
    """Whether labels in this pool compete (one winner); softmax ``p`` is attached."""
    canonical = resolve_taxonomy(pool_slug)
    return canonical is not None and TAXONOMIES[canonical].exclusive


def _join_english(parts: list[str] | tuple[str, ...]) -> str:
    items = list(parts)
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])} and {items[-1]}"


def colour_probe_items() -> list[ScoreItem]:
    """Solid and mix captions for the model's colour vocabulary."""
    items: list[ScoreItem] = []
    for label in MODEL_COLOURS:
        key = _normalise_label(label)
        if key.endswith(" mix"):
            hue = key.removesuffix(" mix").strip() or key
            items.append(ScoreItem(label, f"a multicolour garment with {hue} hues", "mix"))
            continue
        if key in _COLOUR_NON_FEATURED:
            items.append(ScoreItem(label, "a multicolour garment", "solid"))
            continue
        items.append(ScoreItem(label, f"a garment that is {key} in colour", "solid"))
        items.append(ScoreItem(f"{label} mix", f"a multicolour garment with {key} hues", "mix"))
    return items


def featured_solid_colours(
    scored: list[dict[str, float | str]],
    *,
    limit: int = _COLOUR_COMBINATION_SIZE,
) -> list[str]:
    """Highest-scoring solid colours, excluding catch-all multi."""
    featured: list[str] = []
    for entry in sorted(scored, key=lambda item: float(item["score"]), reverse=True):
        if entry.get("kind") != "solid":
            continue
        value = str(entry["value"])
        if _normalise_label(value) in _COLOUR_NON_FEATURED:
            continue
        featured.append(value)
        if len(featured) == limit:
            break
    return featured


def colour_combination_items(featured: list[str]) -> list[ScoreItem]:
    """One named combination of the top 3 featured colours."""
    if len(featured) < _COLOUR_COMBINATION_SIZE:
        return []
    combo = tuple(featured[:_COLOUR_COMBINATION_SIZE])
    return [
        ScoreItem(
            _join_english(combo),
            f"a garment featuring {_join_english([_normalise_label(part) for part in combo])}",
            "combination",
        )
    ]


def graphic_motif_items() -> list[ScoreItem]:
    """Graphic-theme catalog for the optional ``subjects`` pool."""
    return [ScoreItem(value, caption) for value, caption in GRAPHIC_SUBJECTS]


def pattern_probe_items() -> list[ScoreItem]:
    """Pattern-structure captions from the fixed vocabulary."""
    return [ScoreItem(label, caption_for_label("pattern", label)) for label in MODEL_PATTERNS]


def pattern_application_probe_items() -> list[ScoreItem]:
    """Print-application captions from the fixed vocabulary."""
    return [ScoreItem(label, caption_for_label("pattern-application", label)) for label in MODEL_PATTERN_APPLICATIONS]


def embellishment_probe_items() -> list[ScoreItem]:
    """Embellishment captions from the fixed vocabulary."""
    return [ScoreItem(label, caption_for_label("embellishment", label)) for label in MODEL_EMBELLISHMENTS]


def lustre_probe_items() -> list[ScoreItem]:
    """Lustre captions from the fixed vocabulary."""
    return [ScoreItem(label, caption_for_label("lustre", label)) for label in MODEL_LUSTRES]


def appearance_probe_items() -> list[ScoreItem]:
    """Combined appearance captions across the warehouse Appearance attribute group."""
    items: list[ScoreItem] = []
    for slug in APPEARANCE_MEMBER_SLUGS:
        items.extend(prompts_for_pool(slug))
    return items


def product_type_probe_items() -> list[ScoreItem]:
    """Garment-type captions from the fixed vocabulary."""
    items: list[ScoreItem] = []
    for label in MODEL_GARMENT_TYPES:
        article, _spoken = _product_type_phrase(label)
        items.append(ScoreItem(label, _product_type_caption(label), article=article))
    return items


def prompts_for_pool(pool_slug: str) -> list[ScoreItem]:
    """Build the CLIP captions that will be scored for one pool."""
    canonical = resolve_taxonomy(pool_slug)
    if canonical is None:
        raise ValueError(f"unsupported taxonomy: {pool_slug}")
    if canonical == "colour":
        return colour_probe_items()
    if canonical == "subjects":
        return graphic_motif_items()
    if canonical == "product-type":
        return product_type_probe_items()
    if canonical == "pattern":
        return pattern_probe_items()
    if canonical == "pattern-application":
        return pattern_application_probe_items()
    if canonical == "embellishment":
        return embellishment_probe_items()
    if canonical == "lustre":
        return lustre_probe_items()
    if canonical == "appearance":
        return appearance_probe_items()
    if canonical in STYLE_POOLS:
        return style_probe_items(canonical)
    raise ValueError(f"unsupported taxonomy: {pool_slug}")


def unknown_option_keys(raw_options: dict[str, object]) -> list[str]:
    """Return option keys that are not recognised classifiers."""
    unknown: list[str] = []
    for key in raw_options:
        if resolve_taxonomy(key) is None:
            unknown.append(key)
    return unknown
