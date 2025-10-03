# Geonorge/SOSI Code Documentation

This document contains the codes used in the Norwegian Geonorge/Kartverket trail database (Turrutebasen), their Norwegian expansions, and sources where available.

## Code Tables by Column

### Objekttype (Object Types)
Object type identifiers.

| Value | Norwegian     | English Translation | Source | Confidence |
|-------|---------------|-------------------|---------|------------|
| Fotrute | Fotrute       | Hiking trail | Direct | ✓ Confirmed |
| AnnenRute | Annen rute    | Other trail | Direct | ✓ Confirmed |
| Skiløype | Skiløype      | Ski trail | Direct | ✓ Confirmed |
| Sykkelrute | Sykkelrute    | Bike trail | Direct | ✓ Confirmed |
| RuteInfoPunkt | Ruteinformasjonspunkt | Trail information point | Direct | ✓ Confirmed |

Remarks:
* **Column:** objtype

### RuteFølger (Route Follows)
**Norwegian:** Hoveddelen av type trase som ruta følger.
**English:** The main type of route that the trail follows.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| BV | Bilvei | Car road | Bilvei, uspesifisert vegdekke | Car road, unspecified surface |
| FO | Fortau | Sidewalk | Den delen av en bygate som er reservert fotgjengere | The part of a city street reserved for pedestrians |
| GS | Gangvei | Pedestrian/bike path | Bane for fotgjengere og syklister langs eller nær en kjøreveg. Brøytes normalt om vinteren | Path for pedestrians and cyclists along or near a road. Usually plowed in winter |
| IT | I terreng | In terrain | Ruta følger en trase som ikke har tydelige spor i terrenget etter ferdsel | Route follows a path with no visible tracks from traffic |
| LT | Opparbeidet løypetrase | Prepared trail route | Løypetrase der terrenget er utjevnet f.eks. ved rydding av stein eller påfylling av masse | Trail route where terrain is leveled, e.g. by clearing stones or filling |
| SB | Skogsbilvei | Forest road | Skogsbilveger er veger som bygges for å åpne skogsområder for uttransportering av tømmer | Forest roads built to open forest areas for timber transport |
| SF | Sykkelfelt | Bike lane | Sykkelfelt i kjørebanen | Bike lane in the roadway |
| ST | Sti | Path/trail | Godt synlig sti ryddet for vegetasjon, men uten eller med liten grad av opparbeidet grunn | Clearly visible path cleared of vegetation, but with little or no prepared ground |
| SV | Sykkelvei | Bike path | Bane for syklister | Path for cyclists |
| TR | Traktorvei | Tractor road | Traktorveg er veg som hele (eller deler av) året ikke egner seg for vanlig bilkjøring, men som er farbar med traktor | Road unsuitable for regular cars all or part of the year, but passable by tractor |
| TV | Turvei | Hiking road | Turvei er opparbeidet og med toppdekke som gir jevn overflate når det er bar mark | Prepared hiking road with surface giving even ground when snow-free |
| US | Utydelig sti | Unclear path | Sti som er vanskelig å se, f.eks. over bart fjell eller gjengrodd | Path difficult to see, e.g. over bare rock or overgrown |
| VV | Vann/Vassdrag | Water/waterway | For eksempel en skiløype på isen, eller en padlerute | For example a ski trail on ice, or a paddling route |

Remarks:
* **Column:** rutefolger
* **Source:** [Geonorge - RuteFølger](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_DEDF1E91_B1DC_41fb_8281_31B9F0A30449)

### Rutebredde (Route Width)
**Norwegian:** Minste sti-, sykkelsti- eller skiløypebredde på strekningen (ligger i intervallet).
**English:** Minimum path, bike path or ski trail width on the stretch (within interval).

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| 0 | 0-0.5 m | 0-0.5 m | Bredde mellom 0 og 0,5 meter | Width between 0 and 0.5 meters |
| 1 | 0.5 - opp til 1.5 m | 0.5 - up to 1.5 m | Bredde mellom 0,5 og 1,5 meter | Width between 0.5 and 1.5 meters |
| 2 | 1.5 - opp til 3 m | 1.5 - up to 3 m | Bredde mellom 1,5 og 3 meter | Width between 1.5 and 3 meters |
| 3 | 3 - 6 m | 3 - 6 m | Bredde mellom 3 og 6 meter | Width between 3 and 6 meters |
| 4 | over 6 m | over 6 m | Bredde over 6 meter | Width over 6 meters |

Remarks:
* **Column:** rutebredde
* **Source:** [Geonorge - Rutebredde](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_0A8650A8_1791_4b77_8D62_27C503BFD01A)

### RuteVanskelighetsgrad (Route Difficulty)
**Norwegian:** Angivelse av hvor krevende en rute er, basert på forholdsvis objektive kriterier som underlag, tekniske utfordringer, høydemeter og stigningsgrad/eksponering.
**English:** Indication of how demanding a route is, based on relatively objective criteria such as surface, technical challenges, elevation gain and gradient/exposure.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| G | Enkel (Grønn) | Easy (Green) | **Vandring:** Asfalt, grus, skogsveier og gode stier. <300m høydemeter, <5km lengde. For nybegynnere.<br>**Ski:** Korte løyper uten plogbakker/fiskebeinsbakker. <100m høydemeter. I beskyttet terreng under tregrensen. | **Hiking:** Asphalt, gravel, forest roads and good trails. <300m elevation, <5km length. For beginners.<br>**Skiing:** Short trails without steep climbs. <100m elevation. In sheltered terrain below tree line. |
| B | Middels (Blå) | Medium (Blue) | **Vandring:** Kan ha noe mer krevende partier, steinete men ingen ur. <600m høydemeter, <10km lengde.<br>**Ski:** Mer krevende løyper i skogsterreng, kan gå over tregrensen hvis godt merket. <300m høydemeter. | **Hiking:** May have somewhat challenging sections, rocky but no scree. <600m elevation, <10km length.<br>**Skiing:** More demanding trails in forest terrain, may cross tree line if well marked. <300m elevation. |
| R | Krevende (Rød) | Strenuous (Red) | **Vandring:** Sti, åpent terreng, stein, ur og snaufjell. Bratte helninger og løs stein/myr kan forekomme. <1000m høydemeter, <20km lengde.<br>**Ski:** Løyper i høyfjellsterreng og lange, krevende løyper, gjerne upreparerte. <600m høydemeter. | **Hiking:** Trail, open terrain, rocks, scree and alpine. Steep slopes and loose rock/bog may occur. <1000m elevation, <20km length.<br>**Skiing:** Trails in high mountain terrain and long, demanding trails, often ungroomed. <600m elevation. |
| S | Ekspert (Svart) | Expert (Black) | **Vandring:** Lange turer på krevende stier med toppturer, bratte og vanskelige partier, klyving, smale egger, sva, ur.<br>**Ski:** Lengre og mer krevende løyper enn rød, med bratte stigninger, vanligvis upreparerte. | **Hiking:** Long tours on demanding trails with summit routes, steep and difficult sections, scrambling, narrow ridges, slabs, scree.<br>**Skiing:** Longer and more demanding than red, with steep climbs, usually ungroomed. |
| I | Ikke gradert | Not graded | Rute uten gradering | Route without grading |

Remarks:
* **Column:** gradering
* **Source:** [Geonorge - RuteVanskelighetsgrad](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_2F31DD4D_79B4_4348_A5CC_1DDDAF4E0363)
* **DNT Reference:** [DNT Merkehåndboka](https://www.merkehandboka.no/wp-content/uploads/2021/03/DNT_Merkehandbok_graderingskap_098-103.pdf)

### Sesong (Season)
**Norwegian:** Angir om ruta vedlikeholdes og tilrettelegges som sommer-, vinter- eller helårsrute.
**English:** Indicates whether the route is maintained and facilitated as a summer, winter, or year-round route.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| S | Sommer | Summer | Ruta vedlikeholdes og tilrettelegges som sommerrute | Route maintained and facilitated as a summer route |
| V | Vinter | Winter | Ruta vedlikeholdes og tilrettelegges som vinterrute | Route maintained and facilitated as a winter route |
| H | Helårs | Year-round | Ruta vedlikeholdes og tilrettelegges som helårsrute | Route maintained and facilitated as a year-round route |

Remarks:
* **Column:** sesong
* **Source:** [Geonorge - Sesong](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_EB7F183B_DA9E_4bfc_ADE1_B50BB76C59C8)

### Tilpasning (Accessibility/Suitability)
**Norwegian:** Beskriver om ruta/løypa er tilgjengelig/fremkomlig for grupper med spesielle behov.
**English:** Describes whether the route/trail is accessible/passable for groups with special needs.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| A | Annet | Other | - | Other accessibility types |
| B | Barnevogn | Baby stroller | Rute/løype fremkomlig med barnevogn | Route/trail passable with baby stroller |
| G | Gående | Walking | Rute/løype fremkomlig for gående | Route/trail passable for walking |
| R | Rullestol | Wheelchair | Rute/løype fremkomlig med rullestol | Route/trail passable with wheelchair |
| S | Sykkel | Bicycle | Rute/løype fremkomlig for syklende | Route/trail passable for cycling |

Remarks:
* **Column:** tilpasning
* **Source:** [Geonorge - Tilpasning](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_B0D3ECA6_D554_4377_9D3E_AB2B8F418ECA)

### FriluftslivTilrettelegging (Outdoor Recreation Facilitation)
**Norwegian:** Tilrettelegging som er gjort innenfor friluftslivsområdet.
**English:** Facilitation done within the outdoor recreation area.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| 4 | Benker/bord | Benches/tables | Benker og bord | Benches and tables |
| 5 | Bro | Bridge | Bro | Bridge |
| 6 | Brygge | Wharf/dock | Brygge | Wharf/dock |
| 7 | Bål-/grillplasser | Fire/barbecue sites | Bål- og grillplasser | Fire and barbecue sites |
| 8 | Båtutsettingsrampe | Boat launch ramp | Båtutsettingsrampe | Boat launch ramp |
| 12 | Hytte | Cabin | Hytte | Cabin |
| 13 | Informasjonsskilt/tavle | Information sign/board | Informasjonsskilt eller tavle | Information sign or board |
| 14 | Kiosk/serveringssted | Kiosk/serving place | Kiosk eller serveringssted | Kiosk or serving place |
| 18 | Markbearbeiding | Ground treatment | Markbearbeiding, f.eks. markdekke, drenering, klopplegging | Ground treatment, e.g. surface covering, drainage, boardwalk |
| 22 | Parkeringsplass | Parking area | Parkeringsplass | Parking area |
| 28 | Skitrekk | Ski lift | Skitrekk | Ski lift |
| 30 | Stupebrett/badetrapp | Diving board/swimming ladder | Stupebrett eller badetrapp | Diving board or swimming ladder |
| 32 | Teltplass | Camping site | Teltplass | Camping site |
| 35 | Toalett | Toilet | Toalett | Toilet |
| 38 | Baderampe | Swimming ramp | Baderampe | Swimming ramp |
| 40 | AnnenTilrettelegging | Other facilitation | Annen tilrettelegging | Other facilitation |
| 41 | Badeplass | Swimming area | Badeplass | Swimming area |
| 42 | Hytte betjent | Staffed cabin | Hytte betjent | Staffed cabin |
| 43 | Hytte selvbetjent | Self-service cabin | Hytte selvbetjent | Self-service cabin |
| 44 | Hytte ubetjent | Unstaffed cabin | Hytte ubetjent | Unstaffed cabin |
| 45 | Gapahuk | Lean-to shelter | Gapahuk | Lean-to shelter |
| 46 | Utsiktspunkt | Viewpoint | Utsiktspunkt | Viewpoint |
| 50 | Severdighet | Point of interest | Severdighet | Point of interest |
| 51 | Kulturminne | Cultural heritage site | Kulturminne | Cultural heritage site |
| 52 | Trimpost/turkasse | Exercise checkpoint/hiking box | Trimpost eller turkasse | Exercise checkpoint or hiking box |

Remarks:
* **Column:** tilrettelegging (when used with outdoor recreation data)
* **Source:** [Geonorge - FriluftslivTilrettelegging](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_5D400D36_69DE_4fb0_BA38_CC3ADCD195D0)

### Posisjon Målemetode (Position Measurement Method)
**Norwegian:** Metode for måling av posisjon i grunnriss (x,y).
**English:** Method for measuring position in ground plan (x,y).

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| 10 | Terrengmålt: Uspesifisert måleinstrument | Terrain measured: Unspecified instrument | Målt i terrenget, uspesifisert metode/måleinstrument | Measured in terrain, unspecified method/instrument |
| 11 | Terrengmålt: Totalstasjon | Terrain measured: Total station | Målt i terrenget med totalstasjon | Measured in terrain with total station |
| 12 | Terrengmålt: Teodolitt og el avstandsmåler | Terrain measured: Theodolite and EDM | Målt i terrenget med teodolitt og elektronisk avstandsmåler | Measured in terrain with theodolite and electronic distance meter |
| 13 | Terrengmålt: Teodolitt og målebånd | Terrain measured: Theodolite and tape | Målt i terrenget med teodolitt og målebånd | Measured in terrain with theodolite and measuring tape |
| 14 | Terrengmålt: Ortogonalmetoden | Terrain measured: Orthogonal method | Målt i terrenget, ortogonalmetoden | Measured in terrain, orthogonal method |
| 15 | Utmål | Staking out | Utmål | Staking out |
| 18 | Tatt fra plan | Taken from plan | Tatt fra plan | Taken from plan |
| 19 | Annet | Other | Annet (denne har ingen mening, bør fjernes?) | Other (this has no meaning, should be removed?) |
| 20 | Stereoinstrument | Stereo instrument | Målt i stereoinstrument | Measured with stereo instrument |
| 21 | Aerotriangulert | Aerotriangulated | Aerotriangulert | Aerotriangulated |
| 22 | Stereoinstrument: Analytisk plotter | Stereo instrument: Analytical plotter | Målt i analytisk plotter | Measured with analytical plotter |
| 23 | Stereoinstrument: Autograf | Stereo instrument: Autograph | Målt i autograf | Measured with autograph |
| 24 | Stereoinstrument: Digitalt | Stereo instrument: Digital | Målt i digitalt stereoinstrument | Measured with digital stereo instrument |
| 30 | Scannet fra kart | Scanned from map | Skannet fra kart | Scanned from map |
| 31 | Skannet fra kart: Blyantoriginal | Scanned from map: Pencil original | Skannet fra kart, blyantoriginal | Scanned from map, pencil original |
| 32 | Skannet fra kart: Rissefolie | Scanned from map: Scribe coat | Skannet fra kart, rissefolie | Scanned from map, scribe coat |
| 33 | Skannet fra kart: Transparent folie, god kvalitet | Scanned from map: Transparent film, good quality | Skannet fra kart, transparent folie, god kvalitet | Scanned from map, transparent film, good quality |
| 34 | Skannet fra kart: Transparent folie, mindre god kvalitet | Scanned from map: Transparent film, poor quality | Skannet fra kart, transparent folie, mindre god kvalitet | Scanned from map, transparent film, poor quality |
| 35 | Skannet fra kart: Papirkopi | Scanned from map: Paper copy | Skannet fra kart, papirkopi | Scanned from map, paper copy |
| 36 | Flybåren laserscanner | Airborne laser scanner | Målt med flybåren laserscanner | Measured with airborne laser scanner |
| 37 | Bilbåren laser | Vehicle-mounted laser | Målt med bilbåren laser | Measured with vehicle-mounted laser |
| 38 | Lineær referanse | Linear referencing | Lineær referanse | Linear referencing |
| 40 | Digitalisert på skjerm fra ortofoto | Digitized on screen from orthophoto | Digitalisert på skjerm fra ortofoto | Digitized on screen from orthophoto |
| 41 | Digitalisert på skjerm fra ortofoto: Uspesifisert bildeoppløsning | Digitized from orthophoto: Unspecified resolution | Digitalisert på skjerm fra ortofoto, uspesifisert bildeoppløsning | Digitized on screen from orthophoto, unspecified image resolution |
| 42 | Digitalisert på skjerm fra ortofoto: Bildeoppløsning 0.1 m | Digitized from orthophoto: 0.1 m resolution | Digitalisert på skjerm fra ortofoto, bildeoppløsning 0.1 m | Digitized on screen from orthophoto, 0.1 m image resolution |
| 43 | Digitalisert på skjerm fra ortofoto: Bildeoppløsning 0.2 m | Digitized from orthophoto: 0.2 m resolution | Digitalisert på skjerm fra ortofoto, bildeoppløsning 0.2 m | Digitized on screen from orthophoto, 0.2 m image resolution |
| 44 | Digitalisert på skjerm fra ortofoto: Bildeoppløsning 0.25 m | Digitized from orthophoto: 0.25 m resolution | Digitalisert på skjerm fra ortofoto, bildeoppløsning 0.25 m | Digitized on screen from orthophoto, 0.25 m image resolution |
| 45 | Digitalisert på skjerm fra ortofoto: Bildeoppløsning 0.5 m | Digitized from orthophoto: 0.5 m resolution | Digitalisert på skjerm fra ortofoto, bildeoppløsning 0.5 m | Digitized on screen from orthophoto, 0.5 m image resolution |
| 46 | Digitalisert på skjerm fra ortofoto: Bildeoppløsning 1 m | Digitized from orthophoto: 1 m resolution | Digitalisert på skjerm fra ortofoto, bildeoppløsning 1 m | Digitized on screen from orthophoto, 1 m image resolution |
| 47 | Digitalisert på skjerm fra satellittbilde | Digitized from satellite image | Digitalisert på skjerm fra satellittbilde | Digitized on screen from satellite image |
| 48 | Digitalisert på skjerm fra andre digitale rasterdata | Digitized from other digital raster | Digitalisert på skjerm fra andre digitale rasterdata | Digitized on screen from other digital raster data |
| 49 | Digitalisert på skjerm fra tolkning av seismikk | Digitized from seismic interpretation | Digitalisert på skjerm fra tolkning av seismikk | Digitized on screen from seismic interpretation |
| 50 | Digitaliseringsbord: Uspesifisert | Digitizing table: Unspecified | Digitalisert på digitaliseringsbord, uspesifisert underlag | Digitized on digitizing table, unspecified source |
| 51 | Digitaliseringsbord: Ortofoto eller flybilde | Digitizing table: Orthophoto or aerial | Digitalisert på digitaliseringsbord fra ortofoto eller flybilde | Digitized on digitizing table from orthophoto or aerial image |
| 52 | Digitaliseringsbord: Ortofoto, 0.5 m oppløsning | Digitizing table: Orthophoto 0.5 m | Digitalisert på digitaliseringsbord fra ortofoto, 0.5 m oppløsning | Digitized on digitizing table from orthophoto, 0.5 m resolution |
| 53 | Digitaliseringsbord: Ortofoto, 1 m oppløsning | Digitizing table: Orthophoto 1 m | Digitalisert på digitaliseringsbord fra ortofoto, 1 m oppløsning | Digitized on digitizing table from orthophoto, 1 m resolution |
| 54 | Digitaliseringsbord: Flybilde, uspesifisert målestokk | Digitizing table: Aerial, unspecified scale | Digitalisert på digitaliseringsbord fra flybilde, uspesifisert målestokk | Digitized on digitizing table from aerial image, unspecified scale |
| 55 | Digitaliseringsbord: Flybilde, målestokk 1:5000 | Digitizing table: Aerial 1:5000 | Digitalisert på digitaliseringsbord fra flybilde, målestokk 1:5000 | Digitized on digitizing table from aerial image, scale 1:5000 |
| 56 | Digitaliseringsbord: Kart | Digitizing table: Map | Digitalisert på digitaliseringsbord fra kart | Digitized on digitizing table from map |
| 60 | Genererte data | Generated data | Genererte data | Generated data |
| 61 | Genererte data: Interpolasjon | Generated: Interpolation | Genererte data, interpolasjon | Generated data, interpolation |
| 62 | Genererte data: Fra annen geometri | Generated: From other geometry | Genererte data, fra annen geometri | Generated data, from other geometry |
| 63 | Genererte data: Fra annen geometri, generalisering | Generated: From other geometry, generalized | Genererte data, fra annen geometri, generalisering | Generated data, from other geometry, generalization |
| 64 | Genererte data: Fra annen geometri, sentralpunkt | Generated: From other geometry, center point | Genererte data, fra annen geometri, sentralpunkt | Generated data, from other geometry, center point |
| 65 | Genererte data: Fra annen geometri, til flate | Generated: From other geometry, to area | Genererte data, fra annen geometri, til flate | Generated data, from other geometry, to area |
| 66 | Genererte data: Generert i fra terrengmodell | Generated: From terrain model | Genererte data, generert i fra terrengmodell | Generated data, generated from terrain model |
| 67 | Koordinater hentet fra GAB | Coordinates from GAB | Koordinater hentet fra GAB | Coordinates retrieved from GAB |
| 68 | Koordinater hentet fra JREG | Coordinates from JREG | Koordinater hentet fra JREG | Coordinates retrieved from JREG |
| 69 | Beregnet | Calculated | Beregnet | Calculated |
| 70 | Fastsatt | Determined | Fastsatt | Determined |
| 71 | Fastsatt: Uspesifisert | Determined: Unspecified | Fastsatt, uspesifisert | Determined, unspecified |
| 72 | Fastsatt: Ved skjønn/voldgift | Determined: By assessment/arbitration | Fastsatt ved skjønn/voldgift | Determined by assessment/arbitration |
| 73 | Fastsatt: Ved rettsforlik | Determined: By legal settlement | Fastsatt ved rettsforlik | Determined by legal settlement |
| 74 | Fastsatt: Ved jordskifteavgjørelse | Determined: By land consolidation | Fastsatt ved jordskifteavgjørelse | Determined by land consolidation decision |
| 77 | Fastsatt punkt | Fixed point | Fastsatt punkt | Fixed point |
| 78 | Fastsatt ved dom eller kongelig resolusjon | Determined by judgment or royal decree | Fastsatt ved dom eller kongelig resolusjon | Determined by judgment or royal decree |
| 79 | Annet (spesifiseres i filhode) | Other (specified in file header) | Annet (spesifiseres i filhode) | Other (specified in file header) |
| 80 | Frihåndstegnet | Free-hand drawn | Frihåndstegnet | Free-hand drawn |
| 81 | Frihåndstegnet på kart | Free-hand drawn on map | Frihåndstegnet på kart | Free-hand drawn on map |
| 82 | Frihåndstegnet på skjerm | Free-hand drawn on screen | Frihåndstegnet på skjerm | Free-hand drawn on screen |
| 90 | Treghetsstedfesting | Inertial positioning | Treghetsstedfesting | Inertial positioning |
| 91 | GNSS: Fastpunkt | GNSS: Fixed point | Innmålt med satellittbaserte systemer, fastpunkt | Measured with satellite-based systems, fixed point |
| 92 | GNSS: Kodemåling, enkle målinger | GNSS: Code measurement, single | Innmålt med satellittbaserte systemer, kodemåling, enkle målinger | Measured with satellite-based systems, code measurement, single measurements |
| 93 | GNSS: Kodemåling, middel av flere målinger | GNSS: Code measurement, averaged | Innmålt med satellittbaserte systemer, kodemåling, middel av flere målinger | Measured with satellite-based systems, code measurement, average of multiple |
| 94 | GNSS: Fasemåling, statisk måling | GNSS: Phase measurement, static | Innmålt med satellittbaserte systemer, fasemåling, statisk måling | Measured with satellite-based systems, phase measurement, static |
| 95 | GNSS: Fasemåling, andre metoder | GNSS: Phase measurement, other | Innmålt med satellittbaserte systemer, fasemåling, andre metoder | Measured with satellite-based systems, phase measurement, other methods |
| 96 | GNSS: Fasemåling RTK | GNSS: Phase measurement RTK | Innmålt med satellittbaserte systemer, fasemåling RTK | Measured with satellite-based systems, phase measurement RTK |
| 97 | GNSS: Fasemåling, float-løsning | GNSS: Phase measurement, float solution | Innmålt med satellittbaserte systemer, fasemåling, float-løsning | Measured with satellite-based systems, phase measurement, float solution |
| 99 | Ukjent målemetode | Unknown measurement method | Målemetode er ukjent | Measurement method is unknown |

Remarks:
* **Column:** malemetode
* **Source:** [Geonorge - Målemetode](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_0B631DB0_9972_4e63_981B_2A999E29309E)

### Posisjon Nøyaktighet (Position Accuracy)
**Norwegian:** Antatt posisjonsnøyaktighet i grunnriss (x,y) oppgis i cm. Med posisjonsnøyaktighet menes punktstandardavviket for punkter, samt tverravvik i grunnriss for kurver. Den nøyaktighet som angis på objektet bør være så nær dataobjektets nøyaktighet i forhold til det virkelige objektet som mulig.
**English:** Estimated positional accuracy in ground plan (x,y) is specified in cm. Positional accuracy refers to the standard deviation for points, as well as cross deviation in ground plan for curves. The accuracy specified for the object should be as close as possible to the accuracy of the data object in relation to the actual object.

Remarks:
* **Column:** noyaktighet
* **Source:** [Geonorge - Målemetode](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_FDBC489A_1023_490b_9CDD_D422E286046A)

### Trafikkbelastning (Traffic Load)
**Norwegian:** Grov kategorisering av trafikkbelastning på en strekning.
**English:** Rough categorization of traffic load on a route.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| 1 | Uten motorisert ferdsel | Without motorized traffic | Uten motorisert ferdsel | Without motorized traffic |
| 2 | Lav trafikkbelastning | Low traffic load | Hastigheten er lav og det er lite trafikk | Speed is low and there is little traffic |
| 3 | Noe trafikkbelastning | Some traffic load | Hastigheten er lav ved mye trafikk, eller hastigheten er høy ved lite trafikk | Speed is low with much traffic, or speed is high with little traffic |
| 4 | Noe trafikkbelastning, sykkelfelt på vegen | Some traffic load, bicycle lane on road | Mye trafikk og lav hastighet, men vegen har eget sykkelfelt | Much traffic and low speed, but road has dedicated bicycle lane |
| 5 | Høy trafikkbelastning | High traffic load | Alt som ikke inngår i de fire klassene over. I stor grad strekninger med høy hastighet og/eller høy trafikkmengde | Everything not included in the four classes above. Largely stretches with high speed and/or high traffic volume |

Remarks:
* **Column:** trafikkbelastning
* **Source:** [Geonorge - Trafikkbelastning](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_4CB79A6F_D933_4c72_B236_6BFED7DFA185)

### RuteMerking (Route Marking)
**Norwegian:** Forteller om det er merking langs en rute. Med merking menes markering for å vise veg.
**English:** Tells whether there is marking along a route. Marking means markings to show the way.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| JA | Merket | Marked | Merket rute/løype | Marked route/trail |
| NEI | Ikke merket | Not marked | Ikke merket | Not marked |
| SM | Sesongmerket | Seasonally marked | Brukes for eksempel for kvistet løype | Used for example for cross-country ski trail marked with branches |

Remarks:
* **Column**: merking
* **Source:** [Geonorge - RuteMerking](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_7176078E_A22C_4ddf_9396_A01FF5E37D52)

### Belysning (Lighting)
Indicates whether the route has lighting.

| Code | Norwegian | English Translation | Source | Confidence |
|------|-----------|-------------------|---------|------------|
| JA | Ja | Yes | Standard | ✓ Confirmed |
| NEI | Nei | No | Standard | ✓ Confirmed |

Remarks:
* **Column**: belysning

### Skilting (Signage)
Indicates whether the route has directional signs.

| Code | Norwegian | English Translation | Source | Confidence |
|------|-----------|-------------------|---------|------------|
| JA | Ja | Yes | Standard | ✓ Confirmed |
| NEI | Nei | No | Standard | ✓ Confirmed |

Remarks:
* **Column**: skilting

### Underlagstype (Surface Type)
**Norwegian:** Type underlag på ruta.
**English:** Type of surface on the route.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| 1.0 | Asfalt/betong | Asphalt/concrete | Strekningen har fast dekke av asfalt eller betong | The stretch has a fixed surface of asphalt or concrete |
| 2.0 | Grus | Gravel | Strekningen har grusdekke | The stretch has a gravel surface |
| 3.0 | Naturlig grunn | Natural ground | Strekningen går ikke på opparbeidet grunn, men på sti eller over fjell eller lignende | The stretch does not go on developed ground, but on a path or over rock or similar |
| 4.0 | Annet underlag | Other surface | Strekningen har annen type underlag enn de nevnte | The stretch has a different type of surface than those mentioned |

Remarks:
* **Column:** underlagstype
* **Source:** [SOSI Arkitektum - Underlagstype](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_EC77E9DE_6519_4548_9A18_5D5247D926EA)

### Rutetype (Route Type)
**Norwegian:** Klassifisering av ruter.
**English:** Classification of routes.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| 1.0 | Hovedrute | Main route | Mye brukt rute som utgjør hovedtraseene i løypenettet. Ruter som når inn til og er forbindelser mellom viktige turmål | Frequently used route that forms the main paths in the trail network. Routes reaching and connecting important destinations |
| 2.0 | Forgreningsrute | Branch route | Mye brukt rute som binder sammen hovedløypenettet, og som er supplerende eller alternative ruter til hovedruter | Frequently used route connecting the main trail network, supplementing or providing alternatives to main routes |
| 3.0 | Materute | Alternative route | Rute som utgjør alternative traseer, snarveier eller går til målpunkt. Ofte ikke tilrettelagte ruter | Route providing alternative paths, shortcuts or going to destinations. Often not prepared routes |

Remarks:
* **Column:** rutetype
* **Source:** [SOSI Arkitektum - Rutetype](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_F4D4837F_64BE_485a_B1AC_7A665578B773)

### Rutebetydning (Route Significance)
**Norwegian:** Klassifisering av tur- og friluftsruter etter hvor brukerne av ruta i hovedsak kommer fra.
**English:** Classification of hiking and outdoor routes based on where users mainly come from.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| 1.0 | Nasjonal betydning | National significance | Ruter av nasjonal betydning brukes av folk fra hele landet | Routes of national significance used by people from across the country |
| 2.0 | Regional betydning | Regional significance | Ruter av regional betydning brukes av folk fra regionen | Routes of regional significance used by people from the region |
| 3.0 | Lokal betydning | Local significance | Ruter av lokal betydning brukes primært av lokalbefolkningen | Routes of local significance primarily used by local residents |

Remarks:
* **Column:** rutebetydning
* **Source:** [SOSI Arkitektum - Rutebetydning](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_ABD406FF_C931_47b7_ACCD_00BBC7714250)

### Ryddebredde (Clearing Width)
**Norwegian:** Bredde på trase ryddet for løype i skog. Brukes for skiløyper.
**English:** Width of cleared trail in forest. Used for ski trails.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| 1 | Inntil 2 meter | Up to 2 meters | Ryddebredde inntil 2 meter | Clearing width up to 2 meters |
| 2 | 2-3 meter | 2-3 meters | Ryddebredde mellom 2 og 3 meter | Clearing width between 2 and 3 meters |
| 3 | 3-6 meter | 3-6 meters | Ryddebredde mellom 3 og 6 meter | Clearing width between 3 and 6 meters |
| 4 | Over 6 meter | Over 6 meters | Ryddebredde over 6 meter | Clearing width over 6 meters |

Remarks:
* **Column:** ryddebredde
* **Source:** [Geonorge - Ryddebredde](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_822C1A56_FFC2_43c9_A4B6_F807685EA14C)

### SpesialFotrutetype (Special Hiking Trail Type)
**Norwegian:** Spesielle kategorier for fotruter.
**English:** Special categories for hiking trails.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| AN | Andre spesialfotrutetyper | Other special footpath types | For utdyping av type rute, kan egenskapen 'Informasjon' benyttes | For elaboration on route type, the 'Information' property can be used |
| HF | Historisk ferdselrute | Historical travel route | Pilgrimsled, gammel kongevei, postveger, barnevandringsstier og rallarveier etc. | Pilgrim path, old royal road, postal roads, children's migration paths and navvy roads etc. |
| KT | Kultursti | Cultural trail | Rute med opplysninger om kulturhistoriske emner gjennom skilting eller på annen måte | Route with information about cultural-historical topics through signage or otherwise |
| KY | Kyststi | Coastal trail | Sammenhengende rute for i hovedsak vandring langs sjøen. En kyststi skal i hovedsak gå i eller i umiddelbar nærhet av strandsonen | Continuous route mainly for hiking along the sea. A coastal trail should mainly go in or immediately near the shoreline |
| NT | Natursti | Nature trail | Rute med opplysninger om naturfaglige emner gjennom skilting eller på annen måte | Route with information about natural science topics through signage or otherwise |
| TR | Trimløype | Exercise trail | En rute som er spesielt tilrettelagt med for eksempel faste trim- eller treningsapparater og/eller som ofte brukes til organisert trening | A route specially prepared with for example fixed exercise or training equipment and/or often used for organized training |

Remarks:
* **Column:** spesialfotrutetype
* **Source:** [SOSI Arkitektum - SpesialFotrutetype](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_68962800_F0F1_4c61_9257_7FEF7CAAF3DF)

### SpesialSkiløypeType (Special Ski Trail Type)
**Norwegian:** Spesielle kategorier for skiløyper.
**English:** Special categories for ski trails.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| AN | Annet | Other | - | Other special ski trail types |
| BV | Løype for bevegelseshemmede | Trail for mobility impaired | Løyper som er tilrettelagt for blant annet langrennspiggere. Krever liten kupering og slake kurver | Trails prepared for among others cross-country sit-skiers. Requires little terrain variation and gentle curves |
| HL | Løype for hundekjøring | Dog sledding trail | Løype for folk som kjører med hunder | Trail for people driving with dogs |
| KO | Konkurranseløype | Competition trail | Anbefalt løype for aktive skiløpere. Ofte i tilknytning til anlegg for langrenn og skiskyting | Recommended trail for active skiers. Often connected to cross-country and biathlon facilities |
| RL | Rulleskiløype | Roller ski trail | Trase tilrettelagt for rulleski | Trail prepared for roller skiing |
| SH | Løype for synshemmede | Trail for visually impaired | Enveiskjørt løype med slake kurver og lydfyr. Bør skiltes med at man kan møte blinde skiløpere | One-way trail with gentle curves and sound beacons. Should be signed that you may meet blind skiers |

Remarks:
* **Column:** spesialskiloypetype
* **Source:** [Geonorge - SpesialSkiløypetype](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_53C3ADCD_E9C2_4755_9BCE_EC8C3916DCFF)

### SpesialSykkelrutetype (Special Bike Trail Type)
**Norwegian:** Spesielle kategorier for sykkelruter.
**English:** Special categories for bike trails.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| 1 | Tursykling | Touring cycling | Sykling på vedlikeholdt vei, sykkelvei og lignende | Cycling on maintained roads, bike paths, and similar |
| 2 | Terrengsykling | Mountain biking | Sykling utenfor vedlikeholdt vei og turvei | Cycling outside of maintained roads and hiking trails |
| 3 | Utforsykling | Downhill cycling | Sykling i alpinanlegg og/eller andre tilrettelagte anlegg | Cycling in alpine facilities and/or other prepared facilities |
| 4 | Transportsykling | Transport cycling | Sykkelruter mellom knutepunkt. Eks. på knutepunkt er boligområder, arbeidssted, butikk, skole og lignende | Bicycle routes between nodes such as residential areas, workplaces, shops, schools and similar |
| 9 | Annet | Other | - | Other special bike trail types |

Remarks:
* **Column:** spesialsykkelrutetype
* **Source:** [SOSI Arkitektum - SpesialSykkelrutetype](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_80854CE5_E8F5_4d2c_9F76_8050E4D801E0)

### SpesialAnnenRutetype (Special Other Trail Type)
**Norwegian:** Spesielle kategorier for andre typer ruter.
**English:** Special categories for other types of trails.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| 1 | Padlerute | Paddling route | Rute egnet for padling med kajakk eller kano | Route suitable for paddling with kayak or canoe |
| 2 | Riderute | Horse riding trail | Ruter tilrettelagt for ridning | Routes prepared for horseback riding |
| 3 | Trugerute | Snowshoe trail | Ruter tilrettelagt for å gå med truger | Routes prepared for walking with snowshoes |
| 4 | Via Ferata | Via ferrata (secured climbing route) | Tilrettelagt klatresti | Prepared climbing trail |
| 9 | Annet | Other | - | Other special trail types |

Remarks:
* **Column:** spesialannenrutetype
* **Source:** [Geonorge - SpesialAnnenRutetype](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_70FFA6EE_2925_4199_930E_571E396B51AF)

### Løypepreparering (Trail Preparation)
**Norwegian:** Angivelse av hvordan løypestrekningen er preparert.
**English:** Indication of how the trail stretch is prepared.

| Code | Norwegian | English Translation | Description (Norwegian) | Description (English) |
|------|-----------|-------------------|------------------------|----------------------|
| PM | Maskinpreparert | Machine-prepared | Preparert med løypemaskin | Prepared with trail preparation machine |
| PS | Snøscooterpreparert | Snowmobile-prepared | Preparert med snøscooter | Prepared with snowmobile |
| U | Upreparert eller lite preparert løype | Unprepared or lightly prepared trail | Løype som gås opp av skiløpere eller grunnprepareres vha snøscooter/løypemaskin tidlig i sesongen/ved store snøfall | Trail tracked by skiers or base-prepared with snowmobile/preparation machine early in season/after heavy snowfall |

Remarks:
* **Column:** preparering
* **Source:** [Geonorge - Løypepreparering](https://objektkatalog.geonorge.no/Objekttype/Index/EAID_3E736307_149F_42f0_9572_E614B709A64E)

### Data Sources

- **Direct**: Actual Norwegian words found in the Geonorge Turrutebasen data
- **Context**: Inferred from data patterns and Norwegian language conventions

## Confidence Levels

- **✓ Confirmed**: Found in official documentation or are actual Norwegian words
- **~ Likely**: Strong inference from related systems or logical patterns
- **? Uncertain**: Best guess based on context, needs verification
- **❌ Unknown**: No documentation found and no reasonable inference possible

## Implementation Notes

1. **Context is Critical**: Many codes (S, B, R, G, TR, BV) have different meanings depending on the column they appear in.
2. **Code Expansion vs Translation**: This document covers code → Norwegian expansion. English translation is a separate step.
