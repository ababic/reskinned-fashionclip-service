from __future__ import annotations

import pytest

from src.taxonomies import (
    ACCEPTED_SLUGS,
    APPEARANCE_MEMBER_SLUGS,
    GARMENT_TYPES,
    GRAPHIC_MOTIFS,
    MODEL_COLOURS,
    MODEL_EMBELLISHMENTS,
    MODEL_GARMENT_TYPES,
    MODEL_LUSTRES,
    MODEL_PATTERN_APPLICATIONS,
    MODEL_PATTERNS,
    STYLE_POOL_SLUGS,
    STYLE_POOLS,
    _normalise_label,
    appearance_probe_items,
    caption_for_label,
    colour_combination_items,
    colour_probe_items,
    embellishment_probe_items,
    featured_solid_colours,
    graphic_motif_items,
    lustre_probe_items,
    pattern_application_probe_items,
    pattern_probe_items,
    pool_is_exclusive,
    product_type_probe_items,
    resolve_taxonomy,
    returns_full_pool,
    unknown_option_keys,
)


def test_accepted_slugs_are_the_print_facets_plus_optional_pools() -> None:
    assert ACCEPTED_SLUGS == (
        "pattern-application",
        "pattern",
        "embellishment",
        "lustre",
        "appearance",
        "colour",
        "subjects",
        "product-type",
        "sleeve-length",
        "neckline",
        "trouser-length",
        "skirt-length",
        "dress-length",
        "shorts-style",
    )


def test_resolve_taxonomy_aliases() -> None:
    assert resolve_taxonomy("pattern") == "pattern"
    assert resolve_taxonomy("graphic-theme") is None
    assert resolve_taxonomy("color") == "colour"
    assert resolve_taxonomy("Colour") == "colour"
    assert resolve_taxonomy("product_type") == "product-type"
    assert resolve_taxonomy("lustre") == "lustre"
    assert resolve_taxonomy("texture") is None


def test_unknown_option_keys() -> None:
    assert unknown_option_keys({"pattern": True, "texture": False}) == ["texture"]


@pytest.mark.parametrize(
    ("slug", "label", "expected"),
    [
        (
            "pattern-application",
            "Placement print",
            "a garment with a placement print, decoration confined to one area of the garment",
        ),
        (
            "pattern-application",
            "All-over print",
            "a garment covered entirely in an all-over repeating print",
        ),
        (
            "pattern-application",
            "foil print",
            "a garment whose print or decoration is applied as foil print",
        ),
        ("pattern", "Floral", "a garment with a floral pattern"),
        ("pattern", "Stripe", "a garment with a striped pattern"),
        ("pattern", "Ikat", "a garment with an ikat pattern"),
        (
            "pattern",
            "Flames",
            "a garment with a repeating flames print pattern, not a single fire motif",
        ),
        (
            "embellishment",
            "Embroidered",
            "a garment with raised stitched embroidery on the fabric, not a printed design",
        ),
        (
            "lustre",
            "Matte",
            "the garment's fabric has a flat matte finish that absorbs light without shine",
        ),
        (
            "lustre",
            "Glitter",
            (
                "the garment's fabric has fine glitter particles embedded in the finish, "
                "not attached sequins or a glitter print"
            ),
        ),
        ("colour", "Black", "a garment that is black in colour"),
        ("color", "Gray", "a garment that is gray in colour"),
        ("colour", "forest green", "a garment that is forest green in colour"),
        ("product-type", "Leggings", "a photo of leggings"),
        ("product_type", "Dress", "a photo of a dress"),
        ("product-type", "Cape", "a photo of a cape"),
        ("product-type", "Jeans", "a photo of jeans"),
        ("product-type", "Onesie", "a photo of a onesie"),
        ("product-type", "Overshirt", "a photo of an overshirt"),
        ("product-type", "Boxer Shorts", "a photo of boxer shorts"),
        ("product-type", "Boxer short", "a photo of boxer shorts"),
        ("product-type", "Beach Trousers", "a photo of beach trousers"),
        ("product-type", "Beach Trouser", "a photo of beach trousers"),
        ("product-type", "2-Piece Suit", "a photo of a two-piece suit"),
        ("product-type", "Suit 2 Piece", "a photo of a two-piece suit"),
        ("product-type", "Sports Leggings", "a photo of leggings"),
        ("product-type", "Starter Bra", "a photo of a bra"),
        ("product-type", "Casual Shirt", "a photo of a casual shirt"),
        ("product-type", "Camisole", "a photo of a camisole"),
        ("product-type", "Cami", "a photo of a camisole"),
        ("product-type", "High Heels", "a photo of high heels"),
        ("product-type", "High heals", "a photo of high heels"),
        ("product-type", "Brogues", "a photo of brogues"),
        ("product-type", "Running Shoes", "a photo of running shoes"),
        ("product-type", "Tennis Shoes", "a photo of tennis shoes"),
        ("product-type", "Plimsolls", "a photo of plimsolls"),
        ("product-type", "Plimsoles", "a photo of plimsolls"),
        ("product-type", "Oxfords", "a photo of oxfords"),
        ("product-type", "Court Shoes", "a photo of court shoes"),
        ("product-type", "Mules", "a photo of mules"),
        ("product-type", "Espadrilles", "a photo of espadrilles"),
        ("product-type", "Chelsea Boots", "a photo of chelsea boots"),
        ("product-type", "Combat Boots", "a photo of combat boots"),
        ("product-type", "Cowboy Boots", "a photo of cowboy boots"),
        ("product-type", "High-Tops", "a photo of high-tops"),
        ("product-type", "Platform Trainers", "a photo of platform trainers"),
        ("product-type", "Skate Shoes", "a photo of skate shoes"),
    ],
)
def test_caption_for_label(slug: str, label: str, expected: str) -> None:
    assert caption_for_label(slug, label) == expected


def test_caption_for_label_rejects_unknown_taxonomy() -> None:
    with pytest.raises(ValueError, match="unsupported taxonomy"):
        caption_for_label("texture", "Smooth")


def test_style_pools_have_fixed_exclusive_probes() -> None:
    assert STYLE_POOL_SLUGS == (
        "sleeve-length",
        "neckline",
        "trouser-length",
        "skirt-length",
        "dress-length",
        "shorts-style",
    )
    assert all(STYLE_POOLS[slug] for slug in STYLE_POOL_SLUGS)
    assert all(
        len({value.casefold() for value, _caption in STYLE_POOLS[slug]}) == len(STYLE_POOLS[slug])
        for slug in STYLE_POOL_SLUGS
    )
    shorts = dict(STYLE_POOLS["shorts-style"])
    assert shorts["Cargo Shorts"] == "a pair of cargo shorts"
    assert shorts["Running Shorts"] == "a pair of running shorts"
    assert shorts["Cycling Shorts"] == "a pair of cycling shorts"
    assert caption_for_label("shorts-style", "Cargo Shorts") == shorts["Cargo Shorts"]
    trouser_lengths = dict(STYLE_POOLS["trouser-length"])
    assert trouser_lengths["Three-Quarter Length"] == "a pair of three-quarter length trousers"
    assert trouser_lengths["Full Length"] == "a pair of full-length trousers"


def test_all_pools_return_full_ranked_lists() -> None:
    for slug in ACCEPTED_SLUGS:
        assert returns_full_pool(slug)
    assert caption_for_label("colour", "Black") == caption_for_label("colour", "black")


def test_pattern_pools_use_hardcoded_vocabularies() -> None:
    pattern_values = [item.value for item in pattern_probe_items()]
    application_values = [item.value for item in pattern_application_probe_items()]
    assert pattern_values == list(MODEL_PATTERNS)
    assert application_values == list(MODEL_PATTERN_APPLICATIONS)
    assert len(pattern_values) == 49
    assert "Flames" in pattern_values
    assert len(application_values) == 12
    assert "Lustre" not in application_values
    assert "Plain" not in pattern_values
    assert "Embroidery" not in application_values
    assert "Placement print" in application_values
    assert "Damask" in pattern_values
    assert "Stripey" in pattern_values
    assert "Spotty" in pattern_values
    assert "Batik" not in pattern_values
    assert "Tie-dye" not in pattern_values
    assert "Batik" in application_values
    assert list(MODEL_EMBELLISHMENTS) == [
        "Appliquéd",
        "Beaded",
        "Diamante",
        "Embroidered",
        "Fringe",
        "Lace trim",
        "Sequin",
    ]
    assert list(MODEL_LUSTRES) == [
        "Glitter",
        "Glossy",
        "Holographic",
        "Iridescent",
        "Matte",
        "Pearlescent",
        "Shimmer",
        "Sparkly",
    ]
    assert [item.value for item in lustre_probe_items()] == list(MODEL_LUSTRES)


def test_product_type_uses_hardcoded_garment_vocabulary() -> None:
    values = [item.value for item in product_type_probe_items()]
    assert values == list(MODEL_GARMENT_TYPES)
    assert len(values) == 141
    assert values[0] == "Bag"
    assert "Jeggings" in values
    assert "Camisole" in values
    assert {
        "Brogues",
        "Flats",
        "High Heels",
        "Hiking Boots",
        "Loafers",
        "Mary Janes",
        "Mules",
        "Oxfords",
        "Court Shoes",
        "Chelsea Boots",
        "Chukka Boots",
        "Combat Boots",
        "Cowboy Boots",
        "Knee-High Boots",
        "Riding Boots",
        "Sheepskin Boots",
        "Espadrilles",
        "Flip-flops",
        "Clogs",
        "Plimsolls",
        "Running Shoes",
        "Tennis Shoes",
        "High-Tops",
        "Platform Trainers",
        "Skate Shoes",
        "Basketball Shoes",
        "Slip-on Trainers",
        "Wedges",
        "Wellington Boots",
    } <= set(values)
    assert "Shoe" in values and "Shoes" in values
    assert "Vests & Cami" not in values
    assert "Casual Shirt" in values and "Formal Shirt" in values
    assert "Cape" in values
    assert "Towel Robe" in values
    assert "Beach Trousers" in values
    assert "Boxer Shorts" in values
    assert "2-Piece Suit" in values
    assert "Suit 2 Piece" not in values
    assert "Knitwear" not in values
    assert "Curtains" not in values
    assert "Towel" not in values
    assert "Bedding set" not in values
    assert "Calf Sleeve" not in values
    assert "Arm Sleeve" not in values
    assert "Leg Sleeve" not in values
    assert "Beach Trouser" not in values
    assert "Pant" not in values
    assert "Trunk" not in values
    assert "Power Leggings" not in values
    assert "Sports Leggings" not in values
    assert "Swim Leggings" not in values
    assert "Starter Bra" not in values
    assert "Dog coat" not in values
    assert "Pramsuit" not in values
    assert "Sleeping Bag" not in values
    assert "Vests & Cami" not in values
    assert "Swimming Trunks" not in values
    assert "Football Boots" not in values
    assert "Jackets" not in values
    assert "Nighty" not in values
    assert "Outfit" not in values
    assert "Outfits & Sets" not in values
    assert "Set" not in values
    assert "Beach Outfit" not in values
    assert "Jacket" in values
    assert "Nightie" in values
    assert "Hoodie & Joggers Set" in values
    assert "Boot" in values and "Boots" in values
    assert "Shoe" in values and "Shoes" in values
    assert caption_for_label("product-type", "Kimono") == "a photo of a kimono"
    by_value = {item.value: item for item in GARMENT_TYPES}
    assert by_value["Dress"].article == "a"
    assert by_value["Trousers"].article == ""
    assert by_value["Beach Trousers"].article == ""
    assert by_value["Overshirt"].article == "an"
    assert "Jackets" in by_value["Jacket"].aliases
    assert "Nighty" in by_value["Nightie"].aliases
    assert "Cami" in by_value["Camisole"].aliases
    assert "Beach Trouser" in by_value["Beach Trousers"].aliases
    assert {item.value: item.article for item in product_type_probe_items()}["Dress"] == "a"
    assert {item.value: item.article for item in product_type_probe_items()}["Trousers"] == ""


def test_product_type_catalog_has_unique_values_and_aliases() -> None:
    names = [item.value for item in GARMENT_TYPES]
    normalised_names = [_normalise_label(name) for name in names]
    assert len(normalised_names) == len(set(normalised_names))

    alias_targets: dict[str, str] = {}
    for item in GARMENT_TYPES:
        for alias in item.aliases:
            key = _normalise_label(alias)
            previous = alias_targets.setdefault(key, item.value)
            assert previous == item.value


def test_exclusive_pools_are_the_single_winner_taxonomies() -> None:
    assert pool_is_exclusive("pattern")
    assert pool_is_exclusive("pattern-application")
    assert pool_is_exclusive("embellishment")
    assert pool_is_exclusive("lustre")
    assert pool_is_exclusive("appearance")
    assert pool_is_exclusive("product_type")
    assert not pool_is_exclusive("colour")
    assert not pool_is_exclusive("subjects")
    assert not pool_is_exclusive("graphic-theme")


def test_graphic_theme_probes_the_inventory_catalog() -> None:
    items = graphic_motif_items()
    values = [item.value for item in items]
    captions = {item.value: item.caption for item in items}
    assert values == list(GRAPHIC_MOTIFS)
    assert len(values) == 45
    assert captions["Safari"] == "the garment features a lion, monkey or elephant motif, not an animal print"
    assert captions["Mermaids"] == "the garment features a mermaid motif, not an anchor or fish"
    assert captions["Warriors"] == (
        "the garment features a samurai, ronin or ninja motif, not a knight or comic character"
    )
    assert captions["Vehicles"] == ("the garment features a car, motorcycle, airplane, train or truck motif")
    assert "animal print" in captions["Pets"]
    assert "snake print" in captions["Reptiles"]
    assert "heart" in captions["Romance"]
    assert "knight" in captions["Fairy tale"]
    assert "princess" in captions["Medieval"]
    assert "owl" in captions["Birds"]
    assert "moon" in captions["Celestial"]
    assert "strawberry" in captions["Fruit"]
    assert "wolf" in captions["Wildlife"]
    assert "palm" in captions["Tropical"]
    assert "Lion" not in values
    assert "Leopard" not in values


def test_colour_probe_uses_model_vocabulary() -> None:
    items = colour_probe_items()
    values = [item.value for item in items]
    kinds = {item.value: item.kind for item in items}
    assert set(MODEL_COLOURS) <= set(values)
    assert kinds["Black"] == "solid"
    assert kinds["Black mix"] == "mix"
    assert kinds["Grey mix"] == "mix"
    assert kinds["Red mix"] == "mix"
    assert kinds["Multi"] == "solid"
    assert "Multi mix" not in kinds
    assert all(item.kind != "combination" for item in items)
    captions = {item.value: item.caption for item in items}
    assert captions["Grey mix"] == "a multicolour garment with grey hues"
    assert captions["Red mix"] == "a multicolour garment with red hues"
    assert captions["Multi"] == "a multicolour garment"


def test_featured_solids_and_combinations() -> None:
    scored: list[dict[str, float | str]] = [
        {"value": "Multi", "score": 0.9, "kind": "solid"},
        {"value": "Navy", "score": 0.8, "kind": "solid"},
        {"value": "Black", "score": 0.7, "kind": "solid"},
        {"value": "Grey mix", "score": 0.85, "kind": "mix"},
        {"value": "Red", "score": 0.4, "kind": "solid"},
        {"value": "Grey", "score": 0.6, "kind": "solid"},
    ]
    featured = featured_solid_colours(scored)
    assert featured == ["Navy", "Black", "Grey"]
    combos = colour_combination_items(featured)
    assert [item.value for item in combos] == ["Navy, Black and Grey"]
    assert combos[0].kind == "combination"
    assert combos[0].caption == "a garment featuring navy, black and grey"
    assert colour_combination_items(["Navy"]) == []
    assert colour_combination_items(["Navy", "Black"]) == []


def test_print_facet_captions_do_not_share_a_generic_template() -> None:
    application = caption_for_label("pattern-application", "Placement print")
    pattern = caption_for_label("pattern", "Floral")
    subjects = {item.value: item.caption for item in graphic_motif_items()}
    assert "applied" in application or "confined" in application
    assert "pattern" in pattern
    assert "lion" in subjects["Safari"]
    assert len({application, pattern, subjects["Safari"]}) == 3


def test_appearance_facets_use_distinct_prompt_families() -> None:
    pattern = caption_for_label("pattern", "Floral")
    application = caption_for_label("pattern-application", "Placement print")
    embellishment = caption_for_label("embellishment", "Sequin")
    lustre = caption_for_label("lustre", "Matte")
    assert "pattern" in pattern
    assert "floral" in pattern
    assert "confined" in application or "area" in application
    assert "attached" in embellishment or "sewn" in embellishment
    assert lustre.startswith("the garment's fabric has")
    assert len({pattern, application, embellishment, lustre}) == 4


def test_appearance_pools_all_warehouse_appearance_facets() -> None:
    items = appearance_probe_items()
    values = [item.value for item in items]
    expected = (
        [item.value for item in pattern_application_probe_items()]
        + [item.value for item in pattern_probe_items()]
        + [item.value for item in embellishment_probe_items()]
        + [item.value for item in lustre_probe_items()]
    )
    assert values == expected
    assert len(values) == 12 + 49 + 7 + 8
    assert APPEARANCE_MEMBER_SLUGS == (
        "pattern-application",
        "pattern",
        "embellishment",
        "lustre",
    )
    assert pool_is_exclusive("appearance")
