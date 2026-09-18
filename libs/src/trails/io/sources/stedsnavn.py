"""Place names from Norway's official register (SSR) via the Geonorge order API.

The register records where a name applies, not where a dot should go. Extended
features such as valleys and rivers are stored as a *MultiPoint*: several
positions along the feature. Half of them are near-coincident duplicates from
alternative spellings, so points are collapsed within a tolerance before use.

Nothing here invents geometry. The register offers no outline for a valley or a
mountain, and a hull drawn through two sampled points would be an invention, so
callers get the positions the register actually asserts::

    source = Source()
    names = source.load_places(codes, name_types=("dal", "skar", "fjell"))
"""

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd

from ..cache import Download as DownloadCache
from ..cache import Object as ObjectCache
from .geonorge_order import KommuneOrderClient

#: Geonorge catalogue entry for the per-municipality Stedsnavn distribution.
METADATA_UUID = "30caed2f-454e-44be-b5cc-26bb5c0110ca"

#: Geometry layers holding named places as points. Areas exist for only a handful
#: of features, so they are not read; the line layer is read separately by
#: :meth:`Source.load_road_names`.
GEOMETRY_LAYERS = ("sted_posisjon", "sted_multipunkt")

#: Layer holding named features that are lines rather than positions.
LINE_LAYER = "sted_senterlinje"

#: ``navneobjekttype`` of a named road in :data:`LINE_LAYER`. It is by far the
#: bulk of that layer — the rest is tunnels, bridges and a stray stream.
ROAD_NAME_TYPE = "adressenavn"

#: Tables carrying the name text, joined to the geometry via ``lokalid``.
NAME_TABLE = "stedsnavn"
SPELLING_TABLE = "skrivemate"

#: Terrain feature types worth labelling on a hiking map.
TERRAIN_NAME_TYPES = (
    "dal",
    "skar",
    "fjell",
    "fjellområde",
    "vann",
    "tjern",
    # **`seterStøl`, the register's own code.** `seter` was in this list from
    # the first day and matched nothing: Kartverket's code list has no such
    # value, and the cache's 172 kinds over eight municipalities did not
    # either. Found by the test that every code the map reads is in the
    # code list (2026-09-18).
    "seterStøl",
    "isbre",
    "foss",
    "elv",
    "li",
    "myr",
    # Slopes and sandy flats. Both are landmarks a walker uses and the register
    # holds few of them: 14 and 32 within 2 km of this park, against 725 terrain
    # names already drawn there. Deliberately not `utmark`, which is a land-use
    # category for a whole tract rather than a feature with a position.
    "bakke",
    "mo",
)

#: What every name type the register has means, in English -- all 291 of
#: Kartverket's *Navneobjekttype* code list, read off register.geonorge.no on
#: 2026-09-18, so that no map ever shows a reader the register's own word.
#: **What the page shows is English; what the register said is kept beside
#: it.** Uwe, 2026-09-18: *"Bitte übersetze alles auf Englisch was direkt in
#: die Anwendung kommt"* -- a popup that read *gammelBosettingsplass* or
#: *viktighetB* was quoting a column value at a reader. A code the list does
#: not know passes through as spelt and is counted, so a new one is visible.
#: Where the register has a fresh-water and a sea variant (*vik* / *vikISjø*)
#: the English is the same word: a map shows where the point stands.
NAME_TYPE_LABELS = {
    "adressenavn": "address name",
    "adressetilleggsnavn": "additional address name",
    "matrikkeladressenavn": "cadastral address name",
    "administrativBydel": "administrative city district",
    "annenAdministrativInndeling": "other administrative division",
    "bydel": "city district",
    "fylke": "county",
    "grunnkrets": "census tract",
    "kommune": "municipality",
    "nasjon": "nation",
    "poststed": "postal place",
    "skolekrets": "school district",
    "sokn": "parish",
    "soneinndelingTilHavs": "maritime zone",
    "statistiskTettsted": "statistical urban settlement",
    "valgkrets": "electoral district",
    "reinbeitedistrikt": "reindeer grazing district",
    "allmenning": "commons",
    "eiendom": "property",
    "eiendomsteig": "detached parcel",
    "landskapsområde": "landscape area",
    "verneområde": "protected area",
    "friluftsområde": "outdoor recreation area",
    "kontinentalsokkel": "continental shelf",
    "by": "town",
    "tettsted": "urban settlement",
    "tettsteddel": "part of an urban settlement",
    "tettbebyggelse": "built-up area",
    "grend": "hamlet",
    "bygdelagBygd": "rural district",
    "boligfelt": "housing estate",
    "hyttefelt": "cabin estate",
    "borettslag": "housing cooperative",
    "boligblokk": "apartment block",
    "eneboligMindreBoligbygg": "house",
    "fritidsbolig": "holiday cabin",
    "boinstitusjon": "residential institution",
    "industriområde": "industrial area",
    "gard": "farm",
    "bruk": "holding",
    "navnegard": "original farm name",
    "gammelBosettingsplass": "former settlement place",
    "historiskBosetting": "historic settlement, abandoned",
    "tuft": "ruin site",
    "seterStøl": "summer farm",
    "stølsSetereiendom": "summer farm property",
    "setervoll": "summer farm meadow",
    "melkeplass": "milking place",
    "byggForJordbrukFiskeOgFangst": "farm, fishing or hunting building",
    "havnehage": "fenced pasture",
    "utmark": "outfield pasture",
    "jorde": "field",
    "eng": "meadow",
    "gjerde": "fence",
    "grind": "gate",
    "oppdrettsanlegg": "farming facility",
    "dal": "valley",
    "dalføre": "major valley",
    "skar": "pass",
    "botn": "cirque",
    "juv": "gorge",
    "senkning": "hollow",
    "søkk": "dip",
    "fjell": "mountain",
    "fjellområde": "mountain area",
    "fjellside": "mountainside",
    "fjellkant": "mountain shoulder",
    "fjellvegg": "rock face",
    "fjellIDagen": "bare rock",
    "sva": "bare rock slab",
    "berg": "rocky hill",
    "topp": "peak",
    "egg": "ridge crest",
    "rygg": "ridge",
    "ås": "ridge hill",
    "høyde": "height",
    "haug": "knoll",
    "hei": "moorland",
    "vidde": "plateau",
    "slette": "plain",
    "mo": "sandy flat",
    "bakke": "slope",
    "li": "hillside",
    "hylle": "ledge",
    "hammar": "overhang",
    "heller": "rock shelter",
    "stup": "precipice",
    "ur": "scree",
    "stein": "boulder",
    "sand": "sand",
    "grotte": "cave",
    "krater": "crater",
    "geologiskStruktur": "geological structure",
    "skredområde": "landslide area",
    "myr": "marsh",
    "våtmarksområde": "wetland",
    "skog": "forest",
    "skogområde": "forest area",
    "skogholt": "grove",
    "isbre": "glacier",
    "fonn": "snowfield",
    "iskuppel": "ice dome",
    "annenTerrengdetalj": "other terrain feature",
    "nes": "headland",
    "nesVedElver": "land between rivers",
    "halvøy": "peninsula",
    "eid": "isthmus",
    "øy": "island",
    "øygruppe": "island group",
    "holme": "islet",
    "strand": "shore",
    "elvemel": "river bank",
    "øyr": "river delta",
    "innsjø": "lake",
    "vann": "lake",
    "tjern": "tarn",
    "pytt": "pool",
    "gruppeAvVann": "group of lakes",
    "gruppeAvTjern": "group of tarns",
    "delAvInnsjø": "part of a lake",
    "delAvVann": "part of a lake",
    "vik": "bay",
    "sund": "sound",
    "elv": "river",
    "bekk": "stream",
    "grøft": "ditch",
    "foss": "waterfall",
    "stryk": "rapids",
    "høl": "pool below rapids",
    "lon": "still reach",
    "elvesving": "river bend",
    "os": "river mouth",
    "kilde": "spring",
    "vad": "ford",
    "grunne": "shoal",
    "båe": "sunken rock",
    "skjær": "skerry",
    "dam": "dam",
    "kanal": "canal",
    "sluse": "lock",
    "fløtningsanlegg": "log-driving structure",
    "annenVanndetalj": "other water feature",
    "vannverk": "waterworks",
    "vannstandsmåler": "water gauge",
    "fjord": "fjord",
    "fjordmunning": "fjord mouth",
    "vågISjø": "inlet",
    "vikISjø": "cove",
    "sundISjø": "strait",
    "sjøstykke": "stretch of sea",
    "havområde": "sea area",
    "havdyp": "deep",
    "havstrøm": "current",
    "nesISjø": "headland",
    "halvøyISjø": "peninsula",
    "eidISjø": "isthmus",
    "øyISjø": "island",
    "øygruppeISjø": "island group",
    "holmeISjø": "islet",
    "holmegruppeISjø": "islet group",
    "skjærISjø": "skerry",
    "båeISjø": "sunken rock",
    "grunneISjø": "shoal",
    "bankeISjø": "bank",
    "banke": "bank",
    "strandISjø": "beach",
    "klakkISjø": "rock knob",
    "revISjø": "reef",
    "korallrev": "coral reef",
    "rasISjø": "submarine slide",
    "bakkeISjø": "submarine slope",
    "bakketoppISjø": "submarine knoll",
    "bassengISjø": "submarine basin",
    "eggISjø": "shelf edge",
    "fjellkjedeISjø": "submarine ridge",
    "fjelltoppISjø": "seamount",
    "hylleISjø": "submarine ledge",
    "moreneryggISjø": "submarine moraine",
    "platåISjø": "submarine plateau",
    "renneKløftISjø": "submarine channel",
    "ryggISjø": "submarine ridge",
    "sadelISjø": "submarine saddle",
    "sokkelISjø": "submarine foot",
    "søkkISjø": "submarine hollow",
    "undersjøiskVegg": "submarine wall",
    "vulkanISjø": "submarine volcano",
    "fiskeplassISjø": "fishing ground",
    "gass-OljefeltISjø": "oil or gas field",
    "sjødetalj": "other sea feature",
    "farledSkipslei": "shipping lane",
    "ferjestrekning": "ferry crossing",
    "ankringsplass": "anchorage",
    "havn": "harbour",
    "småbåthavn": "marina",
    "kai": "quay",
    "ferjekai": "ferry quay",
    "brygge": "jetty",
    "utstikker": "floating pier",
    "molo": "breakwater",
    "stø": "boat landing",
    "fyrstasjon": "lighthouse",
    "fyrlykt": "light",
    "lanterne": "lantern",
    "lysbøye": "light buoy",
    "stake": "spar buoy",
    "båke": "beacon",
    "jernstang": "iron perch",
    "sjøvarde": "sea cairn",
    "sjømerkeMedIndirekteBelysning": "lit sea mark",
    "overett": "leading marks",
    "oljeinstallasjon": "oil installation",
    "kabel": "cable",
    "rørledning": "pipeline",
    "sti": "path",
    "traktorveg": "tractor road",
    "vegstrekning": "road",
    "vegkryss": "road junction",
    "vegsving": "road bend",
    "bakkeVeg": "hill on a road",
    "fjellovergang": "mountain pass road",
    "bru": "bridge",
    "mindreBrukonstruksjon": "small bridge",
    "klopp": "footbridge",
    "tunnel": "tunnel",
    "overbygg": "gallery",
    "vegbom": "road barrier",
    "bomstasjon": "toll station",
    "rasteplass": "rest area",
    "parkeringsplass": "car park",
    "busstopp": "bus stop",
    "busstasjon": "bus station",
    "holdeplass": "halt",
    "stasjon": "station",
    "banestrekning": "railway line",
    "jernbanebru": "railway bridge",
    "jernbanetunnel": "railway tunnel",
    "flyplass": "airport",
    "landingsplass": "airfield",
    "helikopterlandingsplass": "helipad",
    "fjellheis": "cable car",
    "skiheis": "ski lift",
    "taubane": "goods ropeway",
    "alpinanlegg": "ski resort",
    "kraftledning": "power line",
    "kraftgateRørgate": "penstock",
    "kraftstasjon": "power station",
    "kirke": "church",
    "annenBygningForReligionsutøvelse": "other religious building",
    "gravplass": "cemetery",
    "turisthytte": "tourist cabin",
    "hotell": "hotel",
    "pensjonat": "guesthouse",
    "campingplass": "camp site",
    "serveringssted": "restaurant",
    "skole": "school",
    "barnehage": "kindergarten",
    "universitetHøgskole": "university or college",
    "sykehus": "hospital",
    "helseinstitusjon": "care institution",
    "rådhus": "town hall",
    "fengsel": "prison",
    "vaktstasjonBeredsskapsbygning": "emergency services station",
    "militærtByggAnlegg": "military installation",
    "skytefelt": "firing range",
    "skytebane": "shooting range",
    "forskningsstasjon": "research station",
    "museumGalleriBibliotek": "museum, gallery or library",
    "forsamlingshusKulturhus": "community hall",
    "kulturMessehall": "arena",
    "idrettsanlegg": "sports ground",
    "idrettshall": "sports hall",
    "fornøyelsespark": "amusement park",
    "park": "park",
    "torg": "square",
    "badeplass": "bathing place",
    "utsiktspunkt": "viewpoint",
    "severdighet": "sight",
    "offersted": "offering place",
    "grensemerke": "boundary mark",
    "varde": "cairn",
    "annenKulturdetalj": "other cultural feature",
    "forretningsbygg": "commercial building",
    "fabrikk": "factory",
    "annenIndustri-OgLagerbygning": "industrial or storage building",
    "garasjeHangarbygg": "garage or hangar",
    "bergverk": "mine",
    "grustakSteinbrudd": "gravel pit or quarry",
    "torvtak": "peat cutting",
    "fyllplass": "landfill",
    "tømmervelte": "timber landing",
    "tV-Radio-EllerMobiltelefontårn": "telecommunications mast",
}


#: The values the tables did not know, as they passed through. Read by the
#: build after loading and handed to the page, where a drive counts them.
UNTRANSLATED: set[str] = set()


def type_label(value: object) -> str:
    """Say what a name type is, in English; the register's word where none is known."""
    text = str(value)
    if text not in NAME_TYPE_LABELS:
        UNTRANSLATED.add(text)
    return NAME_TYPE_LABELS.get(text, text)


def importance_label(value: object) -> str:
    """The register's importance rank as its letter: ``viktighetB`` reads *B*.

    The rank runs from A, the most prominent, to K; the word before the letter
    is the column's name and says nothing a reader needs.
    """
    text = str(value)
    return text[len("viktighet"):] if text.startswith("viktighet") and len(text) > len("viktighet") else text


#: Places people live in, from a town down to a cluster of houses.
SETTLEMENT_NAME_TYPES = ("by", "tettbebyggelse", "grend", "boligfelt")

#: Farms and smallholdings. Far more numerous than settlements — over a thousand
#: around one national park — and the usual starting point of a walk here.
FARM_NAME_TYPES = ("gard", "bruk")

#: Places people left. ``gammelBosettingsplass`` is the register's own word for
#: a former settlement place -- a farm, a croft or a sæter nobody lives at --
#: and it is the one name type here that says so. Measured around
#: Lomsdal-Visten on 2026-09-18: 119 in the box, 8 inside the park, and it
#: names Gardsjorda, which no hut register and no OSM node does. It is not
#: complete: Strompdalen, abandoned 1954, is still a ``gard`` to the register,
#: so a farm inside a national park is read the same way from the boundary.
FORMER_SETTLEMENT_NAME_TYPES = ("gammelBosettingsplass",)

#: Huts a walker can head for. ``turisthytte`` is the staffed or self-service
#: kind an association runs; the rest are private.
#: `hytte` and `koie` were listed here and are not codes the register has;
#: a cabin somebody may head for is `turisthytte`, and `fritidsbolig` is a
#: private holiday cabin the map has no business pointing a walker at.
HUT_NAME_TYPES = ("turisthytte",)

#: Where a boat puts in. On this coast that is often the only way to a trailhead.
QUAY_NAME_TYPES = ("ferjekai", "kai", "havn")

#: The register's own importance ranking, most prominent first. Useful for
#: deciding label size and which names to draw at all.
IMPORTANCE_ORDER = (
    "viktighetA",
    "viktighetB",
    "viktighetC",
    "viktighetD",
    "viktighetE",
    "viktighetF",
    "viktighetG",
    "viktighetH",
    "viktighetI",
    "viktighetJ",
    "viktighetK",
)


@dataclass(frozen=True)
class SourceMetadata:
    """Provenance of the place-name data."""

    name: str = "Stedsnavn (SSR)"
    provider: str = "Kartverket"
    country: str = "NO"
    url: str = "https://kartkatalog.geonorge.no/metadata/30caed2f-454e-44be-b5cc-26bb5c0110ca"
    license: str = "CC BY 4.0"
    attribution: str = "© Kartverket"


METADATA = SourceMetadata()


def importance_rank(value: object) -> int:
    """Turn an importance code into a sortable rank.

    Args:
        value: A ``sortering`` value such as ``"viktighetC"``

    Returns:
        Zero-based rank, most prominent first; unknown values rank last
    """
    try:
        return IMPORTANCE_ORDER.index(str(value))
    except ValueError:
        return len(IMPORTANCE_ORDER)


class Source:
    """Loader for Norwegian place names, ordered per municipality."""

    def __init__(self, cache_dir: str = ".cache", timeout: int = 600):
        """Initialize the place-name source.

        Args:
            cache_dir: Root directory for caching data
            timeout: HTTP timeout in seconds
        """
        self.cache = ObjectCache(f"{cache_dir}/objects")
        self.downloads = DownloadCache(f"{cache_dir}/downloads")
        self.orders = KommuneOrderClient(METADATA_UUID, "ssr", self.downloads, timeout=timeout)

    def _read_names(self, archive: str) -> pd.Series:
        """Read the main name text for each place in an archive.

        Args:
            archive: Path to a downloaded Stedsnavn archive

        Returns:
            Series mapping place id to its approved main spelling
        """
        layer_path = f"/vsizip/{archive}/{_find_gdb(archive)}"
        names = gpd.read_file(layer_path, layer=NAME_TABLE)
        spellings = gpd.read_file(layer_path, layer=SPELLING_TABLE)

        joined = spellings.merge(names[["objid", "sted_fk", "navnestatus"]], left_on="stedsnavn_fk", right_on="objid")
        main = joined[joined["navnestatus"] == "hovednavn"]
        return main.groupby("sted_fk")["komplettskrivemate"].first()

    def load_road_names(
        self,
        kommune_codes: list[str],
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Load named roads as whole centerlines.

        The register holds a named road as one feature over its full run, where
        a topographic dataset splits the same road into hundreds of fragments.
        That makes this the natural source for road names, and for deciding what
        counts as one road when a reader clicks it.

        It is not a complete road network: only roads that carry an official
        address name are in here, which leaves out about half the private forest
        and farm tracks. Pair it with a geometry source for those.

        Args:
            kommune_codes: Municipality numbers to load
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 with line geometries and the columns
            ``road_id``, ``name``, ``importance``, ``rank`` and ``kommune``.
            ``road_id`` identifies the road itself: names repeat across
            municipalities, so two distinct roads can share one.
        """
        codes = sorted(kommune_codes)
        cache_key = f"ssr_roads2_{'-'.join(codes)}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading road names from cache...")
            cached = self.cache.load(cache_key)
            assert isinstance(cached, gpd.GeoDataFrame)
            return cached

        archives = self.orders.fetch(codes, force_download=force_download)

        frames = []
        for code, archive in archives.items():
            print(f"Reading {LINE_LAYER} for municipality {code}...")
            names = self._read_names(archive)
            frame = gpd.read_file(f"/vsizip/{archive}/{_find_gdb(archive)}", layer=LINE_LAYER)
            frame = frame[frame["navneobjekttype"] == ROAD_NAME_TYPE]
            frame["name"] = frame["lokalid"].astype("int64").map(names)
            frame["kommune"] = code
            # The register's own id, kept because "Havnegata" exists three times
            # over in this area and the name alone cannot tell them apart.
            frame["road_id"] = frame["lokalid"].astype("int64")
            frames.append(frame[["road_id", "name", "sortering", "kommune", "geometry"]])

        merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
        roads = merged[merged["name"].notna() & merged.geometry.notna()].reset_index(drop=True)
        roads = roads.rename(columns={"sortering": "importance"})
        roads["rank"] = roads["importance"].map(importance_rank)
        roads = gpd.GeoDataFrame(roads.to_crs("EPSG:4326"), geometry="geometry", crs="EPSG:4326")

        print(f"Loaded {len(roads):,} named roads")
        self.cache.save(cache_key, roads, metadata={"kommune_codes": codes, "count": len(roads)})
        return roads

    def load_places(
        self,
        kommune_codes: list[str],
        name_types: tuple[str, ...] | None = TERRAIN_NAME_TYPES,
        dedupe_m: float = 50.0,
        force_download: bool = False,
    ) -> gpd.GeoDataFrame:
        """Load named places as individual points.

        MultiPoint features are exploded into one row per position, after
        collapsing positions that lie within ``dedupe_m`` of each other. Around
        half of them reduce to a single point that way; what survives is the set
        of places along a feature where the name genuinely applies, which is what
        a repeated label on a topographic map represents.

        Args:
            kommune_codes: Municipality numbers to load
            name_types: ``navneobjekttype`` values to keep, or None for all
            dedupe_m: Collapse tolerance in metres
            force_download: Re-order and re-download even if cached

        Returns:
            GeoDataFrame in EPSG:4326 with Point geometries and the columns
            ``name``, ``kind``, ``importance``, ``rank``, ``positions`` (how many
            distinct positions the name has) and ``kommune``
        """
        codes = sorted(kommune_codes)
        cache_key = f"ssr_places_{'-'.join(codes)}_{dedupe_m:g}"

        if not force_download and self.cache.exists(cache_key):
            print("Loading place names from cache...")
            places = self.cache.load(cache_key)
            assert isinstance(places, gpd.GeoDataFrame)
        else:
            archives = self.orders.fetch(codes, force_download=force_download)

            frames = []
            for code, archive in archives.items():
                names = self._read_names(archive)
                for layer in GEOMETRY_LAYERS:
                    print(f"Reading {layer} for municipality {code}...")
                    frame = gpd.read_file(f"/vsizip/{archive}/{_find_gdb(archive)}", layer=layer)
                    frame["name"] = frame["lokalid"].astype("int64").map(names)
                    frame["kommune"] = code
                    frames.append(frame[["name", "navneobjekttype", "sortering", "kommune", "geometry"]])

            merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
            places = _explode_positions(merged, dedupe_m)
            places = places.rename(columns={"navneobjekttype": "kind", "sortering": "importance"})
            places["rank"] = places["importance"].map(importance_rank)
            places = gpd.GeoDataFrame(places.to_crs("EPSG:4326"), geometry="geometry", crs="EPSG:4326")

            print(f"Loaded {len(places):,} place-name positions")
            self.cache.save(cache_key, places, metadata={"kommune_codes": codes, "dedupe_m": dedupe_m, "count": len(places)})

        if name_types is not None:
            places = places[places["kind"].isin(name_types)].reset_index(drop=True)
            print(f"  of which terrain names: {len(places):,}")

        return gpd.GeoDataFrame(places, geometry="geometry", crs="EPSG:4326")


def _explode_positions(gdf: gpd.GeoDataFrame, dedupe_m: float) -> gpd.GeoDataFrame:
    """Split multi-position places into one row per distinct position.

    Args:
        gdf: Named places in a metric CRS, with point or multipoint geometries
        dedupe_m: Collapse tolerance in metres

    Returns:
        GeoDataFrame with Point geometries and a ``positions`` column counting
        how many distinct positions the place kept
    """
    named = gdf[gdf["name"].notna() & gdf.geometry.notna()].reset_index(drop=True)
    if named.empty:
        return gpd.GeoDataFrame(
            {column: [] for column in ("name", "navneobjekttype", "sortering", "kommune", "positions")},
            geometry=[],
            crs=gdf.crs,
        )

    exploded = named.explode(index_parts=False)
    exploded = exploded.reset_index(names="feature_index")

    # Snap to a grid so alternative spellings sharing a position collapse.
    grid_x = (exploded.geometry.x / dedupe_m).round().astype("int64")
    grid_y = (exploded.geometry.y / dedupe_m).round().astype("int64")
    exploded["cell"] = grid_x.astype(str) + "/" + grid_y.astype(str)

    deduped = exploded.drop_duplicates(subset=["feature_index", "cell"]).copy()
    deduped["positions"] = deduped["feature_index"].map(deduped.groupby("feature_index").size())

    columns = ["name", "navneobjekttype", "sortering", "kommune", "positions", "geometry"]
    return gpd.GeoDataFrame(deduped[columns].reset_index(drop=True), geometry="geometry", crs=gdf.crs)


def _find_gdb(archive: str) -> str:
    """Locate the file geodatabase directory inside an archive.

    Args:
        archive: Path to the downloaded ZIP file

    Returns:
        Name of the ``.gdb`` directory within the archive

    Raises:
        ValueError: If the archive holds no file geodatabase
    """
    import zipfile

    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.namelist():
            top = entry.split("/")[0]
            if top.endswith(".gdb"):
                return top
    raise ValueError(f"No .gdb found in {archive}")
