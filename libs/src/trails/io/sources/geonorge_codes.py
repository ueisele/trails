"""Code tables for Geonorge/SOSI trail data.

This module contains all the code tables used in the Norwegian Geonorge/Kartverket
trail database (Turrutebasen), with Norwegian values and English translations.
"""

from dataclasses import dataclass

from trails.io.sources.language import Language


@dataclass
class CodeEntry:
    """Language-specific entry for a code."""

    value: str
    description: str


# Language-agnostic code tables organized by column name
CODE_TABLES: dict[str, dict[str, dict[Language, CodeEntry]]] = {
    # Object types - not really codes but included for consistency
    "objtype": {
        "Fotrute": {
            Language.NO: CodeEntry(
                value="Fotrute",
                description="Fotrute",
            ),
            Language.EN: CodeEntry(
                value="Hiking trail",
                description="Hiking trail",
            ),
        },
        "AnnenRute": {
            Language.NO: CodeEntry(
                value="Annen rute",
                description="Annen rute",
            ),
            Language.EN: CodeEntry(
                value="Other trail",
                description="Other trail",
            ),
        },
        "Skiløype": {
            Language.NO: CodeEntry(
                value="Skiløype",
                description="Skiløype",
            ),
            Language.EN: CodeEntry(
                value="Ski trail",
                description="Ski trail",
            ),
        },
        "Sykkelrute": {
            Language.NO: CodeEntry(
                value="Sykkelrute",
                description="Sykkelrute",
            ),
            Language.EN: CodeEntry(
                value="Bike trail",
                description="Bike trail",
            ),
        },
        "RuteInfoPunkt": {
            Language.NO: CodeEntry(
                value="Ruteinformasjonspunkt",
                description="Ruteinformasjonspunkt",
            ),
            Language.EN: CodeEntry(
                value="Trail information point",
                description="Trail information point",
            ),
        },
    },
    # RuteFølger (Route Follows)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_DEDF1E91_B1DC_41fb_8281_31B9F0A30449
    "rutefolger": {
        "BV": {
            Language.NO: CodeEntry(
                value="Bilvei",
                description="Bilvei, uspesifisert vegdekke",
            ),
            Language.EN: CodeEntry(
                value="Car road",
                description="Car road, unspecified surface",
            ),
        },
        "FO": {
            Language.NO: CodeEntry(
                value="Fortau",
                description="Den delen av en bygate som er reservert fotgjengere",
            ),
            Language.EN: CodeEntry(
                value="Sidewalk",
                description="The part of a city street reserved for pedestrians",
            ),
        },
        "GS": {
            Language.NO: CodeEntry(
                value="Gangvei",
                description=("Bane for fotgjengere og syklister langs eller nær en kjøreveg. Brøytes normalt om vinteren"),
            ),
            Language.EN: CodeEntry(
                value="Pedestrian/bike path",
                description=("Path for pedestrians and cyclists along or near a road. Usually plowed in winter"),
            ),
        },
        "IT": {
            Language.NO: CodeEntry(
                value="I terreng",
                description="Ruta følger en trase som ikke har tydelige spor i terrenget etter ferdsel",
            ),
            Language.EN: CodeEntry(
                value="In terrain",
                description="Route follows a path with no visible tracks from traffic",
            ),
        },
        "LT": {
            Language.NO: CodeEntry(
                value="Opparbeidet løypetrase",
                description="Løypetrase der terrenget er utjevnet f.eks. ved rydding av stein eller påfylling av masse",
            ),
            Language.EN: CodeEntry(
                value="Prepared trail route",
                description="Trail route where terrain is leveled, e.g. by clearing stones or filling",
            ),
        },
        "SB": {
            Language.NO: CodeEntry(
                value="Skogsbilvei",
                description="Skogsbilveger er veger som bygges for å åpne skogsområder for uttransportering av tømmer",
            ),
            Language.EN: CodeEntry(
                value="Forest road",
                description="Forest roads built to open forest areas for timber transport",
            ),
        },
        "SF": {
            Language.NO: CodeEntry(
                value="Sykkelfelt",
                description="Sykkelfelt i kjørebanen",
            ),
            Language.EN: CodeEntry(
                value="Bike lane",
                description="Bike lane in the roadway",
            ),
        },
        "ST": {
            Language.NO: CodeEntry(
                value="Sti",
                description="Godt synlig sti ryddet for vegetasjon, men uten eller med liten grad av opparbeidet grunn",
            ),
            Language.EN: CodeEntry(
                value="Path/trail",
                description="Clearly visible path cleared of vegetation, but with little or no prepared ground",
            ),
        },
        "SV": {
            Language.NO: CodeEntry(
                value="Sykkelvei",
                description="Bane for syklister",
            ),
            Language.EN: CodeEntry(
                value="Bike path",
                description="Path for cyclists",
            ),
        },
        "TR": {
            Language.NO: CodeEntry(
                value="Traktorvei",
                description=("Traktorveg er veg som hele (eller deler av) året ikke egner seg for vanlig bilkjøring, men som er farbar med traktor"),
            ),
            Language.EN: CodeEntry(
                value="Tractor road",
                description=("Road unsuitable for regular cars all or part of the year, but passable by tractor"),
            ),
        },
        "TV": {
            Language.NO: CodeEntry(
                value="Turvei",
                description=("Turvei er opparbeidet og med toppdekke som gir jevn overflate når det er bar mark"),
            ),
            Language.EN: CodeEntry(
                value="Hiking road",
                description=("Prepared hiking road with surface giving even ground when snow-free"),
            ),
        },
        "US": {
            Language.NO: CodeEntry(
                value="Utydelig sti",
                description="Sti som er vanskelig å se, f.eks. over bart fjell eller gjengrodd",
            ),
            Language.EN: CodeEntry(
                value="Unclear path",
                description="Path difficult to see, e.g. over bare rock or overgrown",
            ),
        },
        "VV": {
            Language.NO: CodeEntry(
                value="Vann/Vassdrag",
                description="For eksempel en skiløype på isen, eller en padlerute",
            ),
            Language.EN: CodeEntry(
                value="Water/waterway",
                description="For example a ski trail on ice, or a paddling route",
            ),
        },
    },
    # Rutebredde (Route Width)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_0A8650A8_1791_4b77_8D62_27C503BFD01A
    "rutebredde": {
        "0": {
            Language.NO: CodeEntry(
                value="0-0.5 m",
                description="Bredde mellom 0 og 0,5 meter",
            ),
            Language.EN: CodeEntry(
                value="0-0.5 m",
                description="Width between 0 and 0.5 meters",
            ),
        },
        "1": {
            Language.NO: CodeEntry(
                value="0.5 - opp til 1.5 m",
                description="Bredde mellom 0,5 og 1,5 meter",
            ),
            Language.EN: CodeEntry(
                value="0.5 - up to 1.5 m",
                description="Width between 0.5 and 1.5 meters",
            ),
        },
        "2": {
            Language.NO: CodeEntry(
                value="1.5 - opp til 3 m",
                description="Bredde mellom 1,5 og 3 meter",
            ),
            Language.EN: CodeEntry(
                value="1.5 - up to 3 m",
                description="Width between 1.5 and 3 meters",
            ),
        },
        "3": {
            Language.NO: CodeEntry(
                value="3 - 6 m",
                description="Bredde mellom 3 og 6 meter",
            ),
            Language.EN: CodeEntry(
                value="3 - 6 m",
                description="Width between 3 and 6 meters",
            ),
        },
        "4": {
            Language.NO: CodeEntry(
                value="over 6 m",
                description="Bredde over 6 meter",
            ),
            Language.EN: CodeEntry(
                value="over 6 m",
                description="Width over 6 meters",
            ),
        },
    },
    # RuteVanskelighetsgrad (Route Difficulty) / gradering
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_37AABBD4_EC4F_4fc7_8D39_01EDCE18DDFF
    "gradering": {
        "G": {
            Language.NO: CodeEntry(
                value="Enkel (Grønn)",
                description=(
                    "Vandring: Asfalt, grus, skogsveier og gode stier. <300m høydemeter, "
                    "<5km lengde. For nybegynnere. Ski: Korte løyper uten "
                    "plogbakker/fiskebeinsbakker. <100m høydemeter. I beskyttet terreng "
                    "under tregrensen."
                ),
            ),
            Language.EN: CodeEntry(
                value="Easy (Green)",
                description=(
                    "Hiking: Asphalt, gravel, forest roads and good trails. <300m elevation, "
                    "<5km length. For beginners. Skiing: Short trails without steep climbs. "
                    "<100m elevation. In sheltered terrain below tree line."
                ),
            ),
        },
        "B": {
            Language.NO: CodeEntry(
                value="Middels (Blå)",
                description=(
                    "Vandring: Kan ha noe mer krevende partier, steinete men ingen ur. "
                    "<600m høydemeter, <10km lengde. Ski: Mer krevende løyper i skogsterreng, "
                    "kan gå over tregrensen hvis godt merket. <300m høydemeter."
                ),
            ),
            Language.EN: CodeEntry(
                value="Medium (Blue)",
                description=(
                    "Hiking: May have somewhat challenging sections, rocky but no scree. "
                    "<600m elevation, <10km length. Skiing: More demanding trails in forest "
                    "terrain, may cross tree line if well marked. <300m elevation."
                ),
            ),
        },
        "R": {
            Language.NO: CodeEntry(
                value="Krevende (Rød)",
                description=(
                    "Vandring: Sti, åpent terreng, stein, ur og snaufjell. Bratte helninger "
                    "og løs stein/myr kan forekomme. <1000m høydemeter, <20km lengde. "
                    "Ski: Løyper i høyfjellsterreng og lange, krevende løyper, gjerne "
                    "upreparerte. <600m høydemeter."
                ),
            ),
            Language.EN: CodeEntry(
                value="Strenuous (Red)",
                description=(
                    "Hiking: Trail, open terrain, rocks, scree and alpine. Steep slopes "
                    "and loose rock/bog may occur. <1000m elevation, <20km length. "
                    "Skiing: Trails in high mountain terrain and long, demanding trails, "
                    "often ungroomed. <600m elevation."
                ),
            ),
        },
        "S": {
            Language.NO: CodeEntry(
                value="Ekspert (Svart)",
                description=(
                    "Vandring: Lange turer på krevende stier med toppturer, bratte og "
                    "vanskelige partier, klyving, smale egger, sva, ur. Ski: Lengre og mer "
                    "krevende løyper enn rød, med bratte stigninger, vanligvis upreparerte."
                ),
            ),
            Language.EN: CodeEntry(
                value="Expert (Black)",
                description=(
                    "Hiking: Long tours on demanding trails with summit routes, steep and "
                    "difficult sections, scrambling, narrow ridges, slabs, scree. "
                    "Skiing: Longer and more demanding than red, with steep climbs, "
                    "usually ungroomed."
                ),
            ),
        },
        "I": {
            Language.NO: CodeEntry(
                value="Ikke gradert",
                description="Rute uten gradering",
            ),
            Language.EN: CodeEntry(
                value="Not graded",
                description="Route without grading",
            ),
        },
    },
    # Sesong (Season)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_EB7F183B_DA9E_4bfc_ADE1_B50BB76C59C8
    "sesong": {
        "S": {
            Language.NO: CodeEntry(
                value="Sommer",
                description="Ruta vedlikeholdes og tilrettelegges som sommerrute",
            ),
            Language.EN: CodeEntry(
                value="Summer",
                description="Route maintained and facilitated as a summer route",
            ),
        },
        "V": {
            Language.NO: CodeEntry(
                value="Vinter",
                description="Ruta vedlikeholdes og tilrettelegges som vinterrute",
            ),
            Language.EN: CodeEntry(
                value="Winter",
                description="Route maintained and facilitated as a winter route",
            ),
        },
        "H": {
            Language.NO: CodeEntry(
                value="Helårs",
                description="Ruta vedlikeholdes og tilrettelegges som helårsrute",
            ),
            Language.EN: CodeEntry(
                value="Year-round",
                description="Route maintained and facilitated as a year-round route",
            ),
        },
    },
    # Tilpasning (Accessibility/Suitability)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_B0D3ECA6_D554_4377_9D3E_AB2B8F418ECA
    "tilpasning": {
        "A": {
            Language.NO: CodeEntry(
                value="Annet",
                description="-",
            ),
            Language.EN: CodeEntry(
                value="Other",
                description="Other accessibility types",
            ),
        },
        "B": {
            Language.NO: CodeEntry(
                value="Barnevogn",
                description="Rute/løype fremkomlig med barnevogn",
            ),
            Language.EN: CodeEntry(
                value="Baby stroller",
                description="Route/trail passable with baby stroller",
            ),
        },
        "G": {
            Language.NO: CodeEntry(
                value="Gående",
                description="Rute/løype fremkomlig for gående",
            ),
            Language.EN: CodeEntry(
                value="Walking",
                description="Route/trail passable for walking",
            ),
        },
        "R": {
            Language.NO: CodeEntry(
                value="Rullestol",
                description="Rute/løype fremkomlig med rullestol",
            ),
            Language.EN: CodeEntry(
                value="Wheelchair",
                description="Route/trail passable with wheelchair",
            ),
        },
        "S": {
            Language.NO: CodeEntry(
                value="Sykkel",
                description="Rute/løype fremkomlig for syklende",
            ),
            Language.EN: CodeEntry(
                value="Bicycle",
                description="Route/trail passable for cycling",
            ),
        },
    },
    # FriluftslivTilrettelegging (Outdoor Recreation Facilitation)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_5D400D36_69DE_4fb0_BA38_CC3ADCD195D0
    "tilrettelegging": {
        "4": {
            Language.NO: CodeEntry(
                value="Benker/bord",
                description="Benker og bord",
            ),
            Language.EN: CodeEntry(
                value="Benches/tables",
                description="Benches and tables",
            ),
        },
        "5": {
            Language.NO: CodeEntry(
                value="Bro",
                description="Bro",
            ),
            Language.EN: CodeEntry(
                value="Bridge",
                description="Bridge",
            ),
        },
        "6": {
            Language.NO: CodeEntry(
                value="Brygge",
                description="Brygge",
            ),
            Language.EN: CodeEntry(
                value="Wharf/dock",
                description="Wharf/dock",
            ),
        },
        "7": {
            Language.NO: CodeEntry(
                value="Bål-/grillplasser",
                description="Bål- og grillplasser",
            ),
            Language.EN: CodeEntry(
                value="Fire/barbecue sites",
                description="Fire and barbecue sites",
            ),
        },
        "8": {
            Language.NO: CodeEntry(
                value="Båtutsettingsrampe",
                description="Båtutsettingsrampe",
            ),
            Language.EN: CodeEntry(
                value="Boat launch ramp",
                description="Boat launch ramp",
            ),
        },
        "12": {
            Language.NO: CodeEntry(
                value="Hytte",
                description="Hytte",
            ),
            Language.EN: CodeEntry(
                value="Cabin",
                description="Cabin",
            ),
        },
        "13": {
            Language.NO: CodeEntry(
                value="Informasjonsskilt/tavle",
                description="Informasjonsskilt eller tavle",
            ),
            Language.EN: CodeEntry(
                value="Information sign/board",
                description="Information sign or board",
            ),
        },
        "14": {
            Language.NO: CodeEntry(
                value="Kiosk/serveringssted",
                description="Kiosk eller serveringssted",
            ),
            Language.EN: CodeEntry(
                value="Kiosk/serving place",
                description="Kiosk or serving place",
            ),
        },
        "18": {
            Language.NO: CodeEntry(
                value="Markbearbeiding",
                description="Markbearbeiding, f.eks. markdekke, drenering, klopplegging",
            ),
            Language.EN: CodeEntry(
                value="Ground treatment",
                description="Ground treatment, e.g. surface covering, drainage, boardwalk",
            ),
        },
        "22": {
            Language.NO: CodeEntry(
                value="Parkeringsplass",
                description="Parkeringsplass",
            ),
            Language.EN: CodeEntry(
                value="Parking area",
                description="Parking area",
            ),
        },
        "28": {
            Language.NO: CodeEntry(
                value="Skitrekk",
                description="Skitrekk",
            ),
            Language.EN: CodeEntry(
                value="Ski lift",
                description="Ski lift",
            ),
        },
        "30": {
            Language.NO: CodeEntry(
                value="Stupebrett/badetrapp",
                description="Stupebrett eller badetrapp",
            ),
            Language.EN: CodeEntry(
                value="Diving board/swimming ladder",
                description="Diving board or swimming ladder",
            ),
        },
        "32": {
            Language.NO: CodeEntry(
                value="Teltplass",
                description="Teltplass",
            ),
            Language.EN: CodeEntry(
                value="Camping site",
                description="Camping site",
            ),
        },
        "35": {
            Language.NO: CodeEntry(
                value="Toalett",
                description="Toalett",
            ),
            Language.EN: CodeEntry(
                value="Toilet",
                description="Toilet",
            ),
        },
        "38": {
            Language.NO: CodeEntry(
                value="Baderampe",
                description="Baderampe",
            ),
            Language.EN: CodeEntry(
                value="Swimming ramp",
                description="Swimming ramp",
            ),
        },
        "40": {
            Language.NO: CodeEntry(
                value="AnnenTilrettelegging",
                description="Annen tilrettelegging",
            ),
            Language.EN: CodeEntry(
                value="Other facilitation",
                description="Other facilitation",
            ),
        },
        "41": {
            Language.NO: CodeEntry(
                value="Badeplass",
                description="Badeplass",
            ),
            Language.EN: CodeEntry(
                value="Swimming area",
                description="Swimming area",
            ),
        },
        "42": {
            Language.NO: CodeEntry(
                value="Hytte betjent",
                description="Hytte betjent",
            ),
            Language.EN: CodeEntry(
                value="Staffed cabin",
                description="Staffed cabin",
            ),
        },
        "43": {
            Language.NO: CodeEntry(
                value="Hytte selvbetjent",
                description="Hytte selvbetjent",
            ),
            Language.EN: CodeEntry(
                value="Self-service cabin",
                description="Self-service cabin",
            ),
        },
        "44": {
            Language.NO: CodeEntry(
                value="Hytte ubetjent",
                description="Hytte ubetjent",
            ),
            Language.EN: CodeEntry(
                value="Unstaffed cabin",
                description="Unstaffed cabin",
            ),
        },
        "45": {
            Language.NO: CodeEntry(
                value="Gapahuk",
                description="Gapahuk",
            ),
            Language.EN: CodeEntry(
                value="Lean-to shelter",
                description="Lean-to shelter",
            ),
        },
        "46": {
            Language.NO: CodeEntry(
                value="Utsiktspunkt",
                description="Utsiktspunkt",
            ),
            Language.EN: CodeEntry(
                value="Viewpoint",
                description="Viewpoint",
            ),
        },
        "50": {
            Language.NO: CodeEntry(
                value="Severdighet",
                description="Severdighet",
            ),
            Language.EN: CodeEntry(
                value="Point of interest",
                description="Point of interest",
            ),
        },
        "51": {
            Language.NO: CodeEntry(
                value="Kulturminne",
                description="Kulturminne",
            ),
            Language.EN: CodeEntry(
                value="Cultural heritage site",
                description="Cultural heritage site",
            ),
        },
        "52": {
            Language.NO: CodeEntry(
                value="Trimpost/turkasse",
                description="Trimpost eller turkasse",
            ),
            Language.EN: CodeEntry(
                value="Exercise checkpoint/hiking box",
                description="Exercise checkpoint or hiking box",
            ),
        },
    },
    # Trafikkbelastning (Traffic Load)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_4CB79A6F_D933_4c72_B236_6BFED7DFA185
    "trafikkbelastning": {
        "1": {
            Language.NO: CodeEntry(
                value="Uten motorisert ferdsel",
                description="Uten motorisert ferdsel",
            ),
            Language.EN: CodeEntry(
                value="Without motorized traffic",
                description="Without motorized traffic",
            ),
        },
        "2": {
            Language.NO: CodeEntry(
                value="Lav trafikkbelastning",
                description="Hastigheten er lav og det er lite trafikk",
            ),
            Language.EN: CodeEntry(
                value="Low traffic load",
                description="Speed is low and there is little traffic",
            ),
        },
        "3": {
            Language.NO: CodeEntry(
                value="Noe trafikkbelastning",
                description=("Hastigheten er lav ved mye trafikk, eller hastigheten er høy ved lite trafikk"),
            ),
            Language.EN: CodeEntry(
                value="Some traffic load",
                description=("Speed is low with much traffic, or speed is high with little traffic"),
            ),
        },
        "4": {
            Language.NO: CodeEntry(
                value="Noe trafikkbelastning, sykkelfelt på vegen",
                description="Mye trafikk og lav hastighet, men vegen har eget sykkelfelt",
            ),
            Language.EN: CodeEntry(
                value="Some traffic load, bicycle lane on road",
                description="Much traffic and low speed, but road has dedicated bicycle lane",
            ),
        },
        "5": {
            Language.NO: CodeEntry(
                value="Høy trafikkbelastning",
                description=("Alt som ikke inngår i de fire klassene over. I stor grad strekninger med høy hastighet og/eller høy trafikkmengde"),
            ),
            Language.EN: CodeEntry(
                value="High traffic load",
                description=("Everything not included in the four classes above. Largely stretches with high speed and/or high traffic volume"),
            ),
        },
    },
    # Posisjon Målemetode (Position Measurement Method)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_0B631DB0_9972_4e63_981B_2A999E29309E
    "malemetode": {
        "10": {
            Language.NO: CodeEntry(
                value="Terrengmålt: Uspesifisert måleinstrument",
                description="Målt i terrenget, uspesifisert metode/måleinstrument",
            ),
            Language.EN: CodeEntry(
                value="Terrain measured: Unspecified instrument",
                description="Measured in terrain, unspecified method/instrument",
            ),
        },
        "11": {
            Language.NO: CodeEntry(
                value="Terrengmålt: Totalstasjon",
                description="Målt i terrenget med totalstasjon",
            ),
            Language.EN: CodeEntry(
                value="Terrain measured: Total station",
                description="Measured in terrain with total station",
            ),
        },
        "12": {
            Language.NO: CodeEntry(
                value="Terrengmålt: Teodolitt og el avstandsmåler",
                description="Målt i terrenget med teodolitt og elektronisk avstandsmåler",
            ),
            Language.EN: CodeEntry(
                value="Terrain measured: Theodolite and EDM",
                description="Measured in terrain with theodolite and electronic distance meter",
            ),
        },
        "13": {
            Language.NO: CodeEntry(
                value="Terrengmålt: Teodolitt og målebånd",
                description="Målt i terrenget med teodolitt og målebånd",
            ),
            Language.EN: CodeEntry(
                value="Terrain measured: Theodolite and tape",
                description="Measured in terrain with theodolite and measuring tape",
            ),
        },
        "14": {
            Language.NO: CodeEntry(
                value="Terrengmålt: Ortogonalmetoden",
                description="Målt i terrenget, ortogonalmetoden",
            ),
            Language.EN: CodeEntry(
                value="Terrain measured: Orthogonal method",
                description="Measured in terrain, orthogonal method",
            ),
        },
        "15": {
            Language.NO: CodeEntry(
                value="Utmål",
                description="Utmål",
            ),
            Language.EN: CodeEntry(
                value="Staking out",
                description="Staking out",
            ),
        },
        "18": {
            Language.NO: CodeEntry(
                value="Tatt fra plan",
                description="Tatt fra plan",
            ),
            Language.EN: CodeEntry(
                value="Taken from plan",
                description="Taken from plan",
            ),
        },
        "19": {
            Language.NO: CodeEntry(
                value="Annet",
                description="Annet (denne har ingen mening, bør fjernes?)",
            ),
            Language.EN: CodeEntry(
                value="Other",
                description="Other (this has no meaning, should be removed?)",
            ),
        },
        "20": {
            Language.NO: CodeEntry(
                value="Stereoinstrument",
                description="Målt i stereoinstrument",
            ),
            Language.EN: CodeEntry(
                value="Stereo instrument",
                description="Measured with stereo instrument",
            ),
        },
        "21": {
            Language.NO: CodeEntry(
                value="Aerotriangulert",
                description="Aerotriangulert",
            ),
            Language.EN: CodeEntry(
                value="Aerotriangulated",
                description="Aerotriangulated",
            ),
        },
        "22": {
            Language.NO: CodeEntry(
                value="Stereoinstrument: Analytisk plotter",
                description="Målt i analytisk plotter",
            ),
            Language.EN: CodeEntry(
                value="Stereo instrument: Analytical plotter",
                description="Measured with analytical plotter",
            ),
        },
        "23": {
            Language.NO: CodeEntry(
                value="Stereoinstrument: Autograf",
                description="Målt i autograf",
            ),
            Language.EN: CodeEntry(
                value="Stereo instrument: Autograph",
                description="Measured with autograph",
            ),
        },
        "24": {
            Language.NO: CodeEntry(
                value="Stereoinstrument: Digitalt",
                description="Målt i digitalt stereoinstrument",
            ),
            Language.EN: CodeEntry(
                value="Stereo instrument: Digital",
                description="Measured with digital stereo instrument",
            ),
        },
        "30": {
            Language.NO: CodeEntry(
                value="Scannet fra kart",
                description="Skannet fra kart",
            ),
            Language.EN: CodeEntry(
                value="Scanned from map",
                description="Scanned from map",
            ),
        },
        "31": {
            Language.NO: CodeEntry(
                value="Skannet fra kart: Blyantoriginal",
                description="Skannet fra kart, blyantoriginal",
            ),
            Language.EN: CodeEntry(
                value="Scanned from map: Pencil original",
                description="Scanned from map, pencil original",
            ),
        },
        "32": {
            Language.NO: CodeEntry(
                value="Skannet fra kart: Rissefolie",
                description="Skannet fra kart, rissefolie",
            ),
            Language.EN: CodeEntry(
                value="Scanned from map: Scribe coat",
                description="Scanned from map, scribe coat",
            ),
        },
        "33": {
            Language.NO: CodeEntry(
                value="Skannet fra kart: Transparent folie, god kvalitet",
                description="Skannet fra kart, transparent folie, god kvalitet",
            ),
            Language.EN: CodeEntry(
                value="Scanned from map: Transparent film, good quality",
                description="Scanned from map, transparent film, good quality",
            ),
        },
        "34": {
            Language.NO: CodeEntry(
                value="Skannet fra kart: Transparent folie, mindre god kvalitet",
                description="Skannet fra kart, transparent folie, mindre god kvalitet",
            ),
            Language.EN: CodeEntry(
                value="Scanned from map: Transparent film, poor quality",
                description="Scanned from map, transparent film, poor quality",
            ),
        },
        "35": {
            Language.NO: CodeEntry(
                value="Skannet fra kart: Papirkopi",
                description="Skannet fra kart, papirkopi",
            ),
            Language.EN: CodeEntry(
                value="Scanned from map: Paper copy",
                description="Scanned from map, paper copy",
            ),
        },
        "36": {
            Language.NO: CodeEntry(
                value="Flybåren laserscanner",
                description="Målt med flybåren laserscanner",
            ),
            Language.EN: CodeEntry(
                value="Airborne laser scanner",
                description="Measured with airborne laser scanner",
            ),
        },
        "37": {
            Language.NO: CodeEntry(
                value="Bilbåren laser",
                description="Målt med bilbåren laser",
            ),
            Language.EN: CodeEntry(
                value="Vehicle-mounted laser",
                description="Measured with vehicle-mounted laser",
            ),
        },
        "38": {
            Language.NO: CodeEntry(
                value="Lineær referanse",
                description="Lineær referanse",
            ),
            Language.EN: CodeEntry(
                value="Linear referencing",
                description="Linear referencing",
            ),
        },
        "40": {
            Language.NO: CodeEntry(
                value="Digitalisert på skjerm fra ortofoto",
                description="Digitalisert på skjerm fra ortofoto",
            ),
            Language.EN: CodeEntry(
                value="Digitized on screen from orthophoto",
                description="Digitized on screen from orthophoto",
            ),
        },
        "41": {
            Language.NO: CodeEntry(
                value="Digitalisert på skjerm fra ortofoto: Uspesifisert bildeoppløsning",
                description="Digitalisert på skjerm fra ortofoto, uspesifisert bildeoppløsning",
            ),
            Language.EN: CodeEntry(
                value="Digitized from orthophoto: Unspecified resolution",
                description="Digitized on screen from orthophoto, unspecified image resolution",
            ),
        },
        "42": {
            Language.NO: CodeEntry(
                value="Digitalisert på skjerm fra ortofoto: Bildeoppløsning 0.1 m",
                description="Digitalisert på skjerm fra ortofoto, bildeoppløsning 0.1 m",
            ),
            Language.EN: CodeEntry(
                value="Digitized from orthophoto: 0.1 m resolution",
                description="Digitized on screen from orthophoto, 0.1 m image resolution",
            ),
        },
        "43": {
            Language.NO: CodeEntry(
                value="Digitalisert på skjerm fra ortofoto: Bildeoppløsning 0.2 m",
                description="Digitalisert på skjerm fra ortofoto, bildeoppløsning 0.2 m",
            ),
            Language.EN: CodeEntry(
                value="Digitized from orthophoto: 0.2 m resolution",
                description="Digitized on screen from orthophoto, 0.2 m image resolution",
            ),
        },
        "44": {
            Language.NO: CodeEntry(
                value="Digitalisert på skjerm fra ortofoto: Bildeoppløsning 0.25 m",
                description="Digitalisert på skjerm fra ortofoto, bildeoppløsning 0.25 m",
            ),
            Language.EN: CodeEntry(
                value="Digitized from orthophoto: 0.25 m resolution",
                description="Digitized on screen from orthophoto, 0.25 m image resolution",
            ),
        },
        "45": {
            Language.NO: CodeEntry(
                value="Digitalisert på skjerm fra ortofoto: Bildeoppløsning 0.5 m",
                description="Digitalisert på skjerm fra ortofoto, bildeoppløsning 0.5 m",
            ),
            Language.EN: CodeEntry(
                value="Digitized from orthophoto: 0.5 m resolution",
                description="Digitized on screen from orthophoto, 0.5 m image resolution",
            ),
        },
        "46": {
            Language.NO: CodeEntry(
                value="Digitalisert på skjerm fra ortofoto: Bildeoppløsning 1 m",
                description="Digitalisert på skjerm fra ortofoto, bildeoppløsning 1 m",
            ),
            Language.EN: CodeEntry(
                value="Digitized from orthophoto: 1 m resolution",
                description="Digitized on screen from orthophoto, 1 m image resolution",
            ),
        },
        "47": {
            Language.NO: CodeEntry(
                value="Digitalisert på skjerm fra satellittbilde",
                description="Digitalisert på skjerm fra satellittbilde",
            ),
            Language.EN: CodeEntry(
                value="Digitized from satellite image",
                description="Digitized on screen from satellite image",
            ),
        },
        "48": {
            Language.NO: CodeEntry(
                value="Digitalisert på skjerm fra andre digitale rasterdata",
                description="Digitalisert på skjerm fra andre digitale rasterdata",
            ),
            Language.EN: CodeEntry(
                value="Digitized from other digital raster",
                description="Digitized on screen from other digital raster data",
            ),
        },
        "49": {
            Language.NO: CodeEntry(
                value="Digitalisert på skjerm fra tolkning av seismikk",
                description="Digitalisert på skjerm fra tolkning av seismikk",
            ),
            Language.EN: CodeEntry(
                value="Digitized from seismic interpretation",
                description="Digitized on screen from seismic interpretation",
            ),
        },
        "50": {
            Language.NO: CodeEntry(
                value="Digitaliseringsbord: Uspesifisert",
                description="Digitalisert på digitaliseringsbord, uspesifisert underlag",
            ),
            Language.EN: CodeEntry(
                value="Digitizing table: Unspecified",
                description="Digitized on digitizing table, unspecified source",
            ),
        },
        "51": {
            Language.NO: CodeEntry(
                value="Digitaliseringsbord: Ortofoto eller flybilde",
                description="Digitalisert på digitaliseringsbord fra ortofoto eller flybilde",
            ),
            Language.EN: CodeEntry(
                value="Digitizing table: Orthophoto or aerial",
                description="Digitized on digitizing table from orthophoto or aerial image",
            ),
        },
        "52": {
            Language.NO: CodeEntry(
                value="Digitaliseringsbord: Ortofoto, 0.5 m oppløsning",
                description="Digitalisert på digitaliseringsbord fra ortofoto, 0.5 m oppløsning",
            ),
            Language.EN: CodeEntry(
                value="Digitizing table: Orthophoto 0.5 m",
                description="Digitized on digitizing table from orthophoto, 0.5 m resolution",
            ),
        },
        "53": {
            Language.NO: CodeEntry(
                value="Digitaliseringsbord: Ortofoto, 1 m oppløsning",
                description="Digitalisert på digitaliseringsbord fra ortofoto, 1 m oppløsning",
            ),
            Language.EN: CodeEntry(
                value="Digitizing table: Orthophoto 1 m",
                description="Digitized on digitizing table from orthophoto, 1 m resolution",
            ),
        },
        "54": {
            Language.NO: CodeEntry(
                value="Digitaliseringsbord: Flybilde, uspesifisert målestokk",
                description="Digitalisert på digitaliseringsbord fra flybilde, uspesifisert målestokk",
            ),
            Language.EN: CodeEntry(
                value="Digitizing table: Aerial, unspecified scale",
                description="Digitized on digitizing table from aerial image, unspecified scale",
            ),
        },
        "55": {
            Language.NO: CodeEntry(
                value="Digitaliseringsbord: Flybilde, målestokk 1:5000",
                description="Digitalisert på digitaliseringsbord fra flybilde, målestokk 1:5000",
            ),
            Language.EN: CodeEntry(
                value="Digitizing table: Aerial 1:5000",
                description="Digitized on digitizing table from aerial image, scale 1:5000",
            ),
        },
        "56": {
            Language.NO: CodeEntry(
                value="Digitaliseringsbord: Kart",
                description="Digitalisert på digitaliseringsbord fra kart",
            ),
            Language.EN: CodeEntry(
                value="Digitizing table: Map",
                description="Digitized on digitizing table from map",
            ),
        },
        "60": {
            Language.NO: CodeEntry(
                value="Genererte data",
                description="Genererte data",
            ),
            Language.EN: CodeEntry(
                value="Generated data",
                description="Generated data",
            ),
        },
        "61": {
            Language.NO: CodeEntry(
                value="Genererte data: Interpolasjon",
                description="Genererte data, interpolasjon",
            ),
            Language.EN: CodeEntry(
                value="Generated: Interpolation",
                description="Generated data, interpolation",
            ),
        },
        "62": {
            Language.NO: CodeEntry(
                value="Genererte data: Fra annen geometri",
                description="Genererte data, fra annen geometri",
            ),
            Language.EN: CodeEntry(
                value="Generated: From other geometry",
                description="Generated data, from other geometry",
            ),
        },
        "63": {
            Language.NO: CodeEntry(
                value="Genererte data: Fra annen geometri, generalisering",
                description="Genererte data, fra annen geometri, generalisering",
            ),
            Language.EN: CodeEntry(
                value="Generated: From other geometry, generalized",
                description="Generated data, from other geometry, generalization",
            ),
        },
        "64": {
            Language.NO: CodeEntry(
                value="Genererte data: Fra annen geometri, sentralpunkt",
                description="Genererte data, fra annen geometri, sentralpunkt",
            ),
            Language.EN: CodeEntry(
                value="Generated: From other geometry, center point",
                description="Generated data, from other geometry, center point",
            ),
        },
        "65": {
            Language.NO: CodeEntry(
                value="Genererte data: Fra annen geometri, til flate",
                description="Genererte data, fra annen geometri, til flate",
            ),
            Language.EN: CodeEntry(
                value="Generated: From other geometry, to area",
                description="Generated data, from other geometry, to area",
            ),
        },
        "66": {
            Language.NO: CodeEntry(
                value="Genererte data: Generert i fra terrengmodell",
                description="Genererte data, generert i fra terrengmodell",
            ),
            Language.EN: CodeEntry(
                value="Generated: From terrain model",
                description="Generated data, generated from terrain model",
            ),
        },
        "67": {
            Language.NO: CodeEntry(
                value="Koordinater hentet fra GAB",
                description="Koordinater hentet fra GAB",
            ),
            Language.EN: CodeEntry(
                value="Coordinates from GAB",
                description="Coordinates retrieved from GAB",
            ),
        },
        "68": {
            Language.NO: CodeEntry(
                value="Koordinater hentet fra JREG",
                description="Koordinater hentet fra JREG",
            ),
            Language.EN: CodeEntry(
                value="Coordinates from JREG",
                description="Coordinates retrieved from JREG",
            ),
        },
        "69": {
            Language.NO: CodeEntry(
                value="Beregnet",
                description="Beregnet",
            ),
            Language.EN: CodeEntry(
                value="Calculated",
                description="Calculated",
            ),
        },
        "70": {
            Language.NO: CodeEntry(
                value="Fastsatt",
                description="Fastsatt",
            ),
            Language.EN: CodeEntry(
                value="Determined",
                description="Determined",
            ),
        },
        "71": {
            Language.NO: CodeEntry(
                value="Fastsatt: Uspesifisert",
                description="Fastsatt, uspesifisert",
            ),
            Language.EN: CodeEntry(
                value="Determined: Unspecified",
                description="Determined, unspecified",
            ),
        },
        "72": {
            Language.NO: CodeEntry(
                value="Fastsatt: Ved skjønn/voldgift",
                description="Fastsatt ved skjønn/voldgift",
            ),
            Language.EN: CodeEntry(
                value="Determined: By assessment/arbitration",
                description="Determined by assessment/arbitration",
            ),
        },
        "73": {
            Language.NO: CodeEntry(
                value="Fastsatt: Ved rettsforlik",
                description="Fastsatt ved rettsforlik",
            ),
            Language.EN: CodeEntry(
                value="Determined: By legal settlement",
                description="Determined by legal settlement",
            ),
        },
        "74": {
            Language.NO: CodeEntry(
                value="Fastsatt: Ved jordskifteavgjørelse",
                description="Fastsatt ved jordskifteavgjørelse",
            ),
            Language.EN: CodeEntry(
                value="Determined: By land consolidation",
                description="Determined by land consolidation decision",
            ),
        },
        "77": {
            Language.NO: CodeEntry(
                value="Fastsatt punkt",
                description="Fastsatt punkt",
            ),
            Language.EN: CodeEntry(
                value="Fixed point",
                description="Fixed point",
            ),
        },
        "78": {
            Language.NO: CodeEntry(
                value="Fastsatt ved dom eller kongelig resolusjon",
                description="Fastsatt ved dom eller kongelig resolusjon",
            ),
            Language.EN: CodeEntry(
                value="Determined by judgment or royal decree",
                description="Determined by judgment or royal decree",
            ),
        },
        "79": {
            Language.NO: CodeEntry(
                value="Annet (spesifiseres i filhode)",
                description="Annet (spesifiseres i filhode)",
            ),
            Language.EN: CodeEntry(
                value="Other (specified in file header)",
                description="Other (specified in file header)",
            ),
        },
        "80": {
            Language.NO: CodeEntry(
                value="Frihåndstegnet",
                description="Frihåndstegnet",
            ),
            Language.EN: CodeEntry(
                value="Free-hand drawn",
                description="Free-hand drawn",
            ),
        },
        "81": {
            Language.NO: CodeEntry(
                value="Frihåndstegnet på kart",
                description="Frihåndstegnet på kart",
            ),
            Language.EN: CodeEntry(
                value="Free-hand drawn on map",
                description="Free-hand drawn on map",
            ),
        },
        "82": {
            Language.NO: CodeEntry(
                value="Frihåndstegnet på skjerm",
                description="Frihåndstegnet på skjerm",
            ),
            Language.EN: CodeEntry(
                value="Free-hand drawn on screen",
                description="Free-hand drawn on screen",
            ),
        },
        "90": {
            Language.NO: CodeEntry(
                value="Treghetsstedfesting",
                description="Treghetsstedfesting",
            ),
            Language.EN: CodeEntry(
                value="Inertial positioning",
                description="Inertial positioning",
            ),
        },
        "91": {
            Language.NO: CodeEntry(
                value="GNSS: Fastpunkt",
                description="Innmålt med satellittbaserte systemer, fastpunkt",
            ),
            Language.EN: CodeEntry(
                value="GNSS: Fixed point",
                description="Measured with satellite-based systems, fixed point",
            ),
        },
        "92": {
            Language.NO: CodeEntry(
                value="GNSS: Kodemåling, enkle målinger",
                description="Innmålt med satellittbaserte systemer, kodemåling, enkle målinger",
            ),
            Language.EN: CodeEntry(
                value="GNSS: Code measurement, single",
                description=("Measured with satellite-based systems, code measurement, single measurements"),
            ),
        },
        "93": {
            Language.NO: CodeEntry(
                value="GNSS: Kodemåling, middel av flere målinger",
                description="Innmålt med satellittbaserte systemer, kodemåling, middel av flere målinger",
            ),
            Language.EN: CodeEntry(
                value="GNSS: Code measurement, averaged",
                description=("Measured with satellite-based systems, code measurement, average of multiple"),
            ),
        },
        "94": {
            Language.NO: CodeEntry(
                value="GNSS: Fasemåling, statisk måling",
                description="Innmålt med satellittbaserte systemer, fasemåling, statisk måling",
            ),
            Language.EN: CodeEntry(
                value="GNSS: Phase measurement, static",
                description="Measured with satellite-based systems, phase measurement, static",
            ),
        },
        "95": {
            Language.NO: CodeEntry(
                value="GNSS: Fasemåling, andre metoder",
                description="Innmålt med satellittbaserte systemer, fasemåling, andre metoder",
            ),
            Language.EN: CodeEntry(
                value="GNSS: Phase measurement, other",
                description="Measured with satellite-based systems, phase measurement, other methods",
            ),
        },
        "96": {
            Language.NO: CodeEntry(
                value="GNSS: Fasemåling RTK",
                description="Innmålt med satellittbaserte systemer, fasemåling RTK",
            ),
            Language.EN: CodeEntry(
                value="GNSS: Phase measurement RTK",
                description="Measured with satellite-based systems, phase measurement RTK",
            ),
        },
        "97": {
            Language.NO: CodeEntry(
                value="GNSS: Fasemåling, float-løsning",
                description="Innmålt med satellittbaserte systemer, fasemåling, float-løsning",
            ),
            Language.EN: CodeEntry(
                value="GNSS: Phase measurement, float solution",
                description="Measured with satellite-based systems, phase measurement, float solution",
            ),
        },
        "99": {
            Language.NO: CodeEntry(
                value="Ukjent målemetode",
                description="Målemetode er ukjent",
            ),
            Language.EN: CodeEntry(
                value="Unknown measurement method",
                description="Measurement method is unknown",
            ),
        },
    },
    # RuteMerking (Route Marking)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_7176078E_A22C_4ddf_9396_A01FF5E37D52
    "merking": {
        "JA": {
            Language.NO: CodeEntry(
                value="Merket",
                description="Merket rute/løype",
            ),
            Language.EN: CodeEntry(
                value="Marked",
                description="Marked route/trail",
            ),
        },
        "NEI": {
            Language.NO: CodeEntry(
                value="Ikke merket",
                description="Ikke merket",
            ),
            Language.EN: CodeEntry(
                value="Not marked",
                description="Not marked",
            ),
        },
        "SM": {
            Language.NO: CodeEntry(
                value="Sesongmerket",
                description="Brukes for eksempel for kvistet løype",
            ),
            Language.EN: CodeEntry(
                value="Seasonally marked",
                description="Used for example for cross-country ski trail marked with branches",
            ),
        },
    },
    # Belysning (Lighting)
    "belysning": {
        "JA": {
            Language.NO: CodeEntry(
                value="Ja",
                description="Ja",
            ),
            Language.EN: CodeEntry(
                value="Yes",
                description="Yes",
            ),
        },
        "NEI": {
            Language.NO: CodeEntry(
                value="Nei",
                description="Nei",
            ),
            Language.EN: CodeEntry(
                value="No",
                description="No",
            ),
        },
    },
    # Skilting (Signage)
    "skilting": {
        "JA": {
            Language.NO: CodeEntry(
                value="Ja",
                description="Ja",
            ),
            Language.EN: CodeEntry(
                value="Yes",
                description="Yes",
            ),
        },
        "NEI": {
            Language.NO: CodeEntry(
                value="Nei",
                description="Nei",
            ),
            Language.EN: CodeEntry(
                value="No",
                description="No",
            ),
        },
    },
    # Underlagstype (Surface Type)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_EC77E9DE_6519_4548_9A18_5D5247D926EA
    "underlagstype": {
        "1": {
            Language.NO: CodeEntry(
                value="Asfalt/betong",
                description="Strekningen har fast dekke av asfalt eller betong",
            ),
            Language.EN: CodeEntry(
                value="Asphalt/concrete",
                description="The stretch has a fixed surface of asphalt or concrete",
            ),
        },
        "2": {
            Language.NO: CodeEntry(
                value="Grus",
                description="Strekningen har grusdekke",
            ),
            Language.EN: CodeEntry(
                value="Gravel",
                description="The stretch has a gravel surface",
            ),
        },
        "3": {
            Language.NO: CodeEntry(
                value="Naturlig grunn",
                description=("Strekningen går ikke på opparbeidet grunn, men på sti eller over fjell eller lignende"),
            ),
            Language.EN: CodeEntry(
                value="Natural ground",
                description=("The stretch does not go on developed ground, but on a path or over rock or similar"),
            ),
        },
        "4": {
            Language.NO: CodeEntry(
                value="Annet underlag",
                description="Strekningen har annen type underlag enn de nevnte",
            ),
            Language.EN: CodeEntry(
                value="Other surface",
                description="The stretch has a different type of surface than those mentioned",
            ),
        },
    },
    # Rutetype (Route Type)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_F4D4837F_64BE_485a_B1AC_7A665578B773
    "rutetype": {
        "1": {
            Language.NO: CodeEntry(
                value="Hovedrute",
                description=("Mye brukt rute som utgjør hovedtraseene i løypenettet. Ruter som når inn til og er forbindelser mellom viktige turmål"),
            ),
            Language.EN: CodeEntry(
                value="Main route",
                description=(
                    "Frequently used route that forms the main paths in the trail network. Routes reaching and connecting important destinations"
                ),
            ),
        },
        "2": {
            Language.NO: CodeEntry(
                value="Forgreningsrute",
                description=("Mye brukt rute som binder sammen hovedløypenettet, og som er supplerende eller alternative ruter til hovedruter"),
            ),
            Language.EN: CodeEntry(
                value="Branch route",
                description=("Frequently used route connecting the main trail network, supplementing or providing alternatives to main routes"),
            ),
        },
        "3": {
            Language.NO: CodeEntry(
                value="Materute",
                description=("Rute som utgjør alternative traseer, snarveier eller går til målpunkt. Ofte ikke tilrettelagte ruter"),
            ),
            Language.EN: CodeEntry(
                value="Alternative route",
                description=("Route providing alternative paths, shortcuts or going to destinations. Often not prepared routes"),
            ),
        },
    },
    # Rutebetydning (Route Significance)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_ABD406FF_C931_47b7_ACCD_00BBC7714250
    "rutebetydning": {
        "1": {
            Language.NO: CodeEntry(
                value="Nasjonal betydning",
                description="Ruter av nasjonal betydning brukes av folk fra hele landet",
            ),
            Language.EN: CodeEntry(
                value="National significance",
                description="Routes of national significance used by people from across the country",
            ),
        },
        "2": {
            Language.NO: CodeEntry(
                value="Regional betydning",
                description="Ruter av regional betydning brukes av folk fra regionen",
            ),
            Language.EN: CodeEntry(
                value="Regional significance",
                description="Routes of regional significance used by people from the region",
            ),
        },
        "3": {
            Language.NO: CodeEntry(
                value="Lokal betydning",
                description="Ruter av lokal betydning brukes primært av lokalbefolkningen",
            ),
            Language.EN: CodeEntry(
                value="Local significance",
                description="Routes of local significance primarily used by local residents",
            ),
        },
    },
    # Ryddebredde (Clearing Width)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_822C1A56_FFC2_43c9_A4B6_F807685EA14C
    "ryddebredde": {
        "1": {
            Language.NO: CodeEntry(
                value="Inntil 2 meter",
                description="Ryddebredde inntil 2 meter",
            ),
            Language.EN: CodeEntry(
                value="Up to 2 meters",
                description="Clearing width up to 2 meters",
            ),
        },
        "2": {
            Language.NO: CodeEntry(
                value="2-3 meter",
                description="Ryddebredde mellom 2 og 3 meter",
            ),
            Language.EN: CodeEntry(
                value="2-3 meters",
                description="Clearing width between 2 and 3 meters",
            ),
        },
        "3": {
            Language.NO: CodeEntry(
                value="3-6 meter",
                description="Ryddebredde mellom 3 og 6 meter",
            ),
            Language.EN: CodeEntry(
                value="3-6 meters",
                description="Clearing width between 3 and 6 meters",
            ),
        },
        "4": {
            Language.NO: CodeEntry(
                value="Over 6 meter",
                description="Ryddebredde over 6 meter",
            ),
            Language.EN: CodeEntry(
                value="Over 6 meters",
                description="Clearing width over 6 meters",
            ),
        },
    },
    # SpesialFotrutetype (Special Hiking Trail Type)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_68962800_F0F1_4c61_9257_7FEF7CAAF3DF
    "spesialfotrutetype": {
        "AN": {
            Language.NO: CodeEntry(
                value="Andre spesialfotrutetyper",
                description="For utdyping av type rute, kan egenskapen 'Informasjon' benyttes",
            ),
            Language.EN: CodeEntry(
                value="Other special footpath types",
                description="For elaboration on route type, the 'Information' property can be used",
            ),
        },
        "HF": {
            Language.NO: CodeEntry(
                value="Historisk ferdselrute",
                description=("Pilgrimsled, gammel kongevei, postveger, barnevandringsstier og rallarveier etc."),
            ),
            Language.EN: CodeEntry(
                value="Historical travel route",
                description=("Pilgrim path, old royal road, postal roads, children's migration paths and navvy roads etc."),
            ),
        },
        "KT": {
            Language.NO: CodeEntry(
                value="Kultursti",
                description=("Rute med opplysninger om kulturhistoriske emner gjennom skilting eller på annen måte"),
            ),
            Language.EN: CodeEntry(
                value="Cultural trail",
                description=("Route with information about cultural-historical topics through signage or otherwise"),
            ),
        },
        "KY": {
            Language.NO: CodeEntry(
                value="Kyststi",
                description=(
                    "Sammenhengende rute for i hovedsak vandring langs sjøen. En kyststi skal i "
                    "hovedsak gå i eller i umiddelbar nærhet av strandsonen"
                ),
            ),
            Language.EN: CodeEntry(
                value="Coastal trail",
                description=(
                    "Continuous route mainly for hiking along the sea. A coastal trail should mainly go in or immediately near the shoreline"
                ),
            ),
        },
        "NT": {
            Language.NO: CodeEntry(
                value="Natursti",
                description=("Rute med opplysninger om naturfaglige emner gjennom skilting eller på annen måte"),
            ),
            Language.EN: CodeEntry(
                value="Nature trail",
                description=("Route with information about natural science topics through signage or otherwise"),
            ),
        },
        "TR": {
            Language.NO: CodeEntry(
                value="Trimløype",
                description=(
                    "En rute som er spesielt tilrettelagt med for eksempel faste trim- eller "
                    "treningsapparater og/eller som ofte brukes til organisert trening"
                ),
            ),
            Language.EN: CodeEntry(
                value="Exercise trail",
                description=(
                    "A route specially prepared with for example fixed exercise or training equipment and/or often used for organized training"
                ),
            ),
        },
    },
    # SpesialSkiløypeType (Special Ski Trail Type)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_53C3ADCD_E9C2_4755_9BCE_EC8C3916DCFF
    "spesialskiloypetype": {
        "AN": {
            Language.NO: CodeEntry(
                value="Annet",
                description="-",
            ),
            Language.EN: CodeEntry(
                value="Other",
                description="Other special ski trail types",
            ),
        },
        "BV": {
            Language.NO: CodeEntry(
                value="Løype for bevegelseshemmede",
                description=("Løyper som er tilrettelagt for blant annet langrennspiggere. Krever liten kupering og slake kurver"),
            ),
            Language.EN: CodeEntry(
                value="Trail for mobility impaired",
                description=("Trails prepared for among others cross-country sit-skiers. Requires little terrain variation and gentle curves"),
            ),
        },
        "HL": {
            Language.NO: CodeEntry(
                value="Løype for hundekjøring",
                description="Løype for folk som kjører med hunder",
            ),
            Language.EN: CodeEntry(
                value="Dog sledding trail",
                description="Trail for people driving with dogs",
            ),
        },
        "KO": {
            Language.NO: CodeEntry(
                value="Konkurranseløype",
                description=("Anbefalt løype for aktive skiløpere. Ofte i tilknytning til anlegg for langrenn og skiskyting"),
            ),
            Language.EN: CodeEntry(
                value="Competition trail",
                description=("Recommended trail for active skiers. Often connected to cross-country and biathlon facilities"),
            ),
        },
        "RL": {
            Language.NO: CodeEntry(
                value="Rulleskiløype",
                description="Trase tilrettelagt for rulleski",
            ),
            Language.EN: CodeEntry(
                value="Roller ski trail",
                description="Trail prepared for roller skiing",
            ),
        },
        "SH": {
            Language.NO: CodeEntry(
                value="Løype for synshemmede",
                description=("Enveiskjørt løype med slake kurver og lydfyr. Bør skiltes med at man kan møte blinde skiløpere"),
            ),
            Language.EN: CodeEntry(
                value="Trail for visually impaired",
                description=("One-way trail with gentle curves and sound beacons. Should be signed that you may meet blind skiers"),
            ),
        },
    },
    # SpesialSykkelrutetype (Special Bike Trail Type)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_80854CE5_E8F5_4d2c_9F76_8050E4D801E0
    "spesialsykkelrutetype": {
        "1": {
            Language.NO: CodeEntry(
                value="Tursykling",
                description="Sykling på vedlikeholdt vei, sykkelvei og lignende",
            ),
            Language.EN: CodeEntry(
                value="Touring cycling",
                description="Cycling on maintained roads, bike paths, and similar",
            ),
        },
        "2": {
            Language.NO: CodeEntry(
                value="Terrengsykling",
                description="Sykling utenfor vedlikeholdt vei og turvei",
            ),
            Language.EN: CodeEntry(
                value="Mountain biking",
                description="Cycling outside of maintained roads and hiking trails",
            ),
        },
        "3": {
            Language.NO: CodeEntry(
                value="Utforsykling",
                description="Sykling i alpinanlegg og/eller andre tilrettelagte anlegg",
            ),
            Language.EN: CodeEntry(
                value="Downhill cycling",
                description="Cycling in alpine facilities and/or other prepared facilities",
            ),
        },
        "4": {
            Language.NO: CodeEntry(
                value="Transportsykling",
                description=("Sykkelruter mellom knutepunkt. Eks. på knutepunkt er boligområder, arbeidssted, butikk, skole og lignende"),
            ),
            Language.EN: CodeEntry(
                value="Transport cycling",
                description="Bicycle routes between nodes such as residential areas, workplaces, shops, schools and similar",
            ),
        },
        "9": {
            Language.NO: CodeEntry(
                value="Annet",
                description="-",
            ),
            Language.EN: CodeEntry(
                value="Other",
                description="Other special bike trail types",
            ),
        },
    },
    # SpesialAnnenRutetype (Special Other Trail Type)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_70FFA6EE_2925_4199_930E_571E396B51AF
    "spesialannenrutetype": {
        "1": {
            Language.NO: CodeEntry(
                value="Padlerute",
                description="Rute egnet for padling med kajakk eller kano",
            ),
            Language.EN: CodeEntry(
                value="Paddling route",
                description="Route suitable for paddling with kayak or canoe",
            ),
        },
        "2": {
            Language.NO: CodeEntry(
                value="Riderute",
                description="Ruter tilrettelagt for ridning",
            ),
            Language.EN: CodeEntry(
                value="Horse riding trail",
                description="Routes prepared for horseback riding",
            ),
        },
        "3": {
            Language.NO: CodeEntry(
                value="Trugerute",
                description="Ruter tilrettelagt for å gå med truger",
            ),
            Language.EN: CodeEntry(
                value="Snowshoe trail",
                description="Routes prepared for walking with snowshoes",
            ),
        },
        "4": {
            Language.NO: CodeEntry(
                value="Via Ferata",
                description="Tilrettelagt klatresti",
            ),
            Language.EN: CodeEntry(
                value="Via ferrata (secured climbing route)",
                description="Prepared climbing trail",
            ),
        },
        "9": {
            Language.NO: CodeEntry(
                value="Annet",
                description="-",
            ),
            Language.EN: CodeEntry(
                value="Other",
                description="Other special trail types",
            ),
        },
    },
    # Løypepreparering (Trail Preparation)
    # Reference: https://objektkatalog.geonorge.no/Objekttype/Index/EAID_3E736307_149F_42f0_9572_E614B709A64E
    "preparering": {
        "PM": {
            Language.NO: CodeEntry(
                value="Maskinpreparert",
                description="Preparert med løypemaskin",
            ),
            Language.EN: CodeEntry(
                value="Machine-prepared",
                description="Prepared with trail preparation machine",
            ),
        },
        "PS": {
            Language.NO: CodeEntry(
                value="Snøscooterpreparert",
                description="Preparert med snøscooter",
            ),
            Language.EN: CodeEntry(
                value="Snowmobile-prepared",
                description="Prepared with snowmobile",
            ),
        },
        "U": {
            Language.NO: CodeEntry(
                value="Upreparert eller lite preparert løype",
                description=("Løype som gås opp av skiløpere eller grunnprepareres vha snøscooter/løypemaskin tidlig i sesongen/ved store snøfall"),
            ),
            Language.EN: CodeEntry(
                value="Unprepared or lightly prepared trail",
                description=("Trail tracked by skiers or base-prepared with snowmobile/preparation machine early in season/after heavy snowfall"),
            ),
        },
    },
}


# Module-level functions for resolving Geonorge/SOSI codes


def get_entry(column: str, code: str, language: Language = Language.NO) -> CodeEntry | None:
    """Get full entry for a code in specified language.

    Args:
        column: Column name (e.g., "gradering")
        code: Code value (e.g., "G")
        language: Target language

    Returns:
        CodeEntry if found, None otherwise
    """
    if column in CODE_TABLES and code in CODE_TABLES[column]:
        return CODE_TABLES[column][code].get(language)
    return None


def get_value(column: str, code: str, language: Language = Language.NO) -> str:
    """Get expanded value for a code in specified language.

    Args:
        column: Column name (e.g., "gradering")
        code: Code value (e.g., "G")
        language: Target language

    Returns:
        Expanded value if found, original code otherwise
    """
    entry = get_entry(column, code, language)
    return entry.value if entry else code


def get_description(column: str, code: str, language: Language = Language.NO) -> str | None:
    """Get description for a code in specified language.

    Args:
        column: Column name (e.g., "gradering")
        code: Code value (e.g., "G")
        language: Target language

    Returns:
        Description if found, None otherwise
    """
    entry = get_entry(column, code, language)
    return entry.description if entry else None


def get_code(column: str, value: str, language: Language = Language.NO) -> str | None:
    """Get code by its expanded value (reverse lookup).

    Args:
        column: Column name (e.g., "gradering")
        value: Expanded value (e.g., "Enkel (Grønn)" or "Easy (Green)")
        language: Language of the value

    Returns:
        Code if found, None otherwise

    Example:
        code = get_code("gradering", "Enkel (Grønn)", Language.NO)
        # Returns "G"
    """
    if column not in CODE_TABLES:
        return None

    # Search through all codes in this column's table
    for code, lang_entries in CODE_TABLES[column].items():
        if language in lang_entries:
            entry = lang_entries[language]
            if entry.value == value:
                return code

    return None


def has_code_table(column: str) -> bool:
    """Check if column has a code table.

    Args:
        column: Column name to check

    Returns:
        True if column has code table, False otherwise
    """
    return column in CODE_TABLES
