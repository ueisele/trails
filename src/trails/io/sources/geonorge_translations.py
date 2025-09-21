"""
Translation mappings for Geonorge (Kartverket) data.

Contains translations for layer names and column names from Norwegian to English.
"""

from trails.io.sources.language import Language

# Layer name translations
LAYER_TRANSLATIONS = {
    "fotrute_senterlinje": {
        Language.EN: "hiking_trail_centerline",
    },
    "annenrute_senterlinje": {
        Language.EN: "other_trail_centerline",
    },
    "skiloype_senterlinje": {
        Language.EN: "ski_trail_centerline",
    },
    "sykkelrute_senterlinje": {
        Language.EN: "bike_trail_centerline",
    },
    "ruteinfopunkt_posisjon": {
        Language.EN: "trail_info_point_position",
    },
    "fotruteinfo_tabell": {
        Language.EN: "hiking_trail_info_table",
    },
    "annenruteinfo_tabell": {
        Language.EN: "other_trail_info_table",
    },
    "skiloypeinfo_tabell": {
        Language.EN: "ski_trail_info_table",
    },
    "sykkelruteinfo_tabell": {
        Language.EN: "bike_trail_info_table",
    },
}

# Column name translations
COLUMN_TRANSLATIONS = {
    # Common identification columns
    "objtype": {
        Language.EN: "object_type",
    },
    "lokalid": {
        Language.EN: "local_id",
    },
    "navnerom": {
        Language.EN: "namespace",
    },
    "versjonid": {
        Language.EN: "version_id",
    },
    "anleggsnummer": {
        Language.EN: "facility_number",
    },
    "omradeid": {
        Language.EN: "area_id",
    },
    "uukoblingsid": {
        Language.EN: "no_connection_id",
    },
    # Date and time columns
    "datafangstdato": {
        Language.EN: "data_capture_date",
    },
    "oppdateringsdato": {
        Language.EN: "update_date",
    },
    "kopidato": {
        Language.EN: "copy_date",
    },
    # Trail information columns
    "rutenavn": {
        Language.EN: "trail_name",
    },
    "rutenummer": {
        Language.EN: "trail_number",
    },
    "rutefolger": {
        Language.EN: "trail_follows",
    },
    "rutebredde": {
        Language.EN: "trail_width",
    },
    "rutetype": {
        Language.EN: "trail_type",
    },
    "rutebetydning": {
        Language.EN: "trail_significance",
    },
    "ruteinformasjon": {
        Language.EN: "trail_information",
    },
    "ruteinfoid": {
        Language.EN: "trail_info_id",
    },
    "ryddebredde": {
        Language.EN: "clearing_width",
    },
    # Special trail type columns
    "spesialfotrutetype": {
        Language.EN: "special_hiking_trail_type",
    },
    "spesialskiloypetype": {
        Language.EN: "special_ski_trail_type",
    },
    "spesialsykkelrutetype": {
        Language.EN: "special_bike_trail_type",
    },
    "spesialannenrutetype": {
        Language.EN: "special_other_trail_type",
    },
    # Physical attributes
    "merking": {
        Language.EN: "marking",
    },
    "belysning": {
        Language.EN: "lighting",
    },
    "skilting": {
        Language.EN: "signage",
    },
    "underlagstype": {
        Language.EN: "surface_type",
    },
    "sesong": {
        Language.EN: "season",
    },
    "gradering": {
        Language.EN: "difficulty",
    },
    "tilpasning": {
        Language.EN: "accessibility",
    },
    "tilrettelegging": {
        Language.EN: "facilitation",
    },
    "trafikkbelastning": {
        Language.EN: "traffic_load",
    },
    # Maintenance and quality
    "vedlikeholdsansvarlig": {
        Language.EN: "maintenance_responsible",
    },
    "malemetode": {
        Language.EN: "measurement_method",
    },
    "noyaktighet": {
        Language.EN: "accuracy",
    },
    "informasjon": {
        Language.EN: "information",
    },
    "opphav": {
        Language.EN: "origin",
    },
    "originaldatavert": {
        Language.EN: "original_data_host",
    },
    # Ski-specific columns
    "antallskispor": {
        Language.EN: "number_of_ski_tracks",
    },
    "preparering": {
        Language.EN: "preparation",
    },
    "skoytetrase": {
        Language.EN: "skating_track",
    },
    # Foreign key columns
    "fotrute_fk": {
        Language.EN: "hiking_trail_fk",
    },
    "annenrute_fk": {
        Language.EN: "other_trail_fk",
    },
    "skiloype_fk": {
        Language.EN: "ski_trail_fk",
    },
    "sykkelrute_fk": {
        Language.EN: "bike_trail_fk",
    },
    # Geometry columns
    "SHAPE_Length": {
        Language.EN: "SHAPE_Length",
    },
    "geometry": {
        Language.EN: "geometry",
    },
}


def translate_name(name: str, translation_dict: dict[str, dict[Language, str]], language: Language) -> str:
    """
    Translate a name using the translation dictionary.
    Returns original if no translation exists for the given language.

    Args:
        name: The name to translate
        translation_dict: Dictionary with language mappings
        language: Target language

    Returns:
        Translated name or original if no translation exists
    """
    if name in translation_dict and language in translation_dict[name]:
        return translation_dict[name][language]
    return name


def translate_layer_name(name: str, language: Language) -> str:
    """
    Translate a layer name to the target language.

    Args:
        name: Layer name in Norwegian
        language: Target language

    Returns:
        Translated layer name or original if no translation exists
    """
    return translate_name(name, LAYER_TRANSLATIONS, language)


def translate_column_name(name: str, language: Language) -> str:
    """
    Translate a column name to the target language.

    Args:
        name: Column name in Norwegian
        language: Target language

    Returns:
        Translated column name or original if no translation exists
    """
    return translate_name(name, COLUMN_TRANSLATIONS, language)
