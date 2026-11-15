"""Published forms keep the look they have: the existing theme presets are pinned.

A form wears its stored theme (colours are saved inline); a form with no theme
renders the Default preset. A new preset is added next to these and never edits
them, so this test lists every preset that existed before the Daybreak preset
exactly, and fails on any change to one of them, to what new forms start with,
or to the Default preset's resolved values. New presets are not listed here:
they are pinned by their own tests.
"""

from backend.app.constants.themes import (
    LEGACY_PRESET_NAMES,
    NEW_FORM_THEME,
    PRESET_WELCOME_LAYOUTS,
    THEME_STYLES,
    new_form_theme,
    theme_dict,
    themes,
)

PINNED_PRESETS = {'Blossom': {'accent': '#FCE7F3',
             'primary': '#500724',
             'secondary': '#BE185D',
             'tertiary': '#DB2777',
             'title': 'Blossom'},
 'Cherry': {'accent': '#FEE2E2',
            'primary': '#450A0A',
            'secondary': '#B91C1C',
            'tertiary': '#DC2626',
            'title': 'Cherry'},
 'Default': {'accent': '#F5F7FB',
             'primary': '#101828',
             'secondary': '#1649E2',
             'tertiary': '#818CA0',
             'title': 'Default'},
 'Forest': {'accent': '#DCFCE7',
            'primary': '#052E16',
            'secondary': '#15803D',
            'tertiary': '#16A34A',
            'title': 'Forest'},
 'Honey': {'accent': '#FEF3C7',
           'primary': '#422006',
           'secondary': '#A16207',
           'tertiary': '#B45309',
           'title': 'Honey'},
 'Kantlijn': {'accent': '#F8EEEC',
              'background': {'artwork': 'marble',
                             'pattern': 'margin',
                             'type': 'pattern'},
              'bodyFont': 'atkinson-next',
              'buttonStyle': 'filled',
              'dataFont': 'atkinson-mono',
              'highlight': '#A3305A',
              'primary': '#16261F',
              'radius': 'soft',
              'secondary': '#1E4D3B',
              'selection': '#1E4D3B',
              'style': 'classic',
              'tertiary': '#7D8C84',
              'title': 'Kantlijn',
              'titleFont': 'besley',
              'titleWidth': 'normal'},
 'Lavender': {'accent': '#F3E8FF',
              'primary': '#3B0764',
              'secondary': '#7E22CE',
              'tertiary': '#9333EA',
              'title': 'Lavender'},
 'Leaflet': {'accent': '#FFFFFF',
             'primary': '#1A1A1A',
             'secondary': '#0B3D91',
             'style': 'leaflet',
             'tertiary': '#6B7A99',
             'title': 'Leaflet'},
 'Mint': {'accent': '#CCFBF1',
          'primary': '#042F2E',
          'secondary': '#0F766E',
          'tertiary': '#0D9488',
          'title': 'Mint'},
 'Mono': {'accent': '#FFFFFF',
          'primary': '#101826',
          'secondary': '#101826',
          'tertiary': '#767676',
          'title': 'Mono'},
 'Ocean': {'accent': '#DBEAFE',
           'primary': '#111827',
           'secondary': '#1D4ED8',
           'tertiary': '#2563EB',
           'title': 'Ocean'},
 'Paper': {'accent': '#FAF6F0',
           'primary': '#292524',
           'secondary': '#7C2D12',
           'tertiary': '#78716C',
           'title': 'Paper'},
 'Raster': {'accent': '#FFFFFF',
            'background': {'pattern': 'columns', 'type': 'pattern'},
            'bodyFont': 'archivo',
            'buttonStyle': 'outlined',
            'dataFont': 'atkinson-mono',
            'primary': '#0E0E14',
            'radius': 'sharp',
            'secondary': '#2B2FD1',
            'style': 'studio',
            'tertiary': '#6D7083',
            'title': 'Raster',
            'titleFont': 'archivo',
            'titleWidth': 'expanded'},
 'Rose': {'accent': '#FFE4E6',
          'primary': '#4C0519',
          'secondary': '#BE123C',
          'tertiary': '#E11D48',
          'title': 'Rose'},
 'Sky': {'accent': '#CFFAFE',
         'primary': '#083344',
         'secondary': '#0E7490',
         'tertiary': '#0891B2',
         'title': 'Sky'},
 'Slate': {'accent': '#F3F4F6',
           'primary': '#111827',
           'secondary': '#4B5563',
           'tertiary': '#64748B',
           'title': 'Slate'},
 'Sunset': {'accent': '#FFEDD5',
            'primary': '#431407',
            'secondary': '#C2410C',
            'tertiary': '#EA580C',
            'title': 'Sunset'},
 'Twilight': {'accent': '#E0E7FF',
              'primary': '#1E1B4B',
              'secondary': '#4338CA',
              'tertiary': '#4F46E5',
              'title': 'Twilight'}}

PINNED_WELCOME_LAYOUTS = {'Kantlijn': 'TWO_COLUMN_IMAGE_RIGHT',
 'Raster': 'SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN'}

PINNED_DEFAULT_MODEL = {'accent': '#F5F7FB',
 'background': None,
 'bodyFont': None,
 'buttonStyle': None,
 'dataFont': None,
 'highlight': None,
 'inputText': None,
 'primary': '#101828',
 'radius': None,
 'secondary': '#1649E2',
 'selection': None,
 'style': None,
 'tertiary': '#818CA0',
 'title': 'Default',
 'titleFont': None,
 'titleWidth': None}

PINNED_NEW_FORM_MODEL = {'accent': '#FFFFFF',
 'background': None,
 'bodyFont': None,
 'buttonStyle': None,
 'dataFont': None,
 'highlight': None,
 'inputText': None,
 'primary': '#1A1A1A',
 'radius': None,
 'secondary': '#0B3D91',
 'selection': None,
 'style': 'leaflet',
 'tertiary': '#6B7A99',
 'title': 'Leaflet',
 'titleFont': None,
 'titleWidth': None}


def test_every_existing_preset_is_exactly_as_it_was():
    for name, pinned in PINNED_PRESETS.items():
        assert theme_dict[name] == pinned, name


PINNED_ORDER = [
    "Default", "Paper", "Leaflet", "Ocean", "Forest", "Cherry", "Mono", "Sunset",
    "Lavender", "Slate", "Blossom", "Twilight", "Honey", "Mint", "Sky", "Rose",
    "Kantlijn", "Raster",
]  # fmt: skip


def test_the_presets_before_the_pin_keep_their_order():
    assert [n for n in theme_dict if n in PINNED_ORDER] == PINNED_ORDER


def test_the_default_preset_resolves_to_the_same_values():
    assert themes["Default"].model_dump(mode="json") == PINNED_DEFAULT_MODEL


def test_welcome_layouts_of_the_existing_presets_are_unchanged():
    for name, layout in PINNED_WELCOME_LAYOUTS.items():
        assert PRESET_WELCOME_LAYOUTS[name] == layout


def test_legacy_names_and_styles_are_unchanged():
    assert LEGACY_PRESET_NAMES == {'Black': 'Mono',
 'Blue': 'Ocean',
 'Green': 'Forest',
 'Orange': 'Sunset',
 'Purple': 'Lavender',
 'Red': 'Cherry'}
    assert THEME_STYLES == ('classic', 'sheet', 'studio', 'leaflet')


def test_new_forms_start_with_the_same_preset():
    assert NEW_FORM_THEME == 'Leaflet'
    assert new_form_theme().model_dump(mode="json") == PINNED_NEW_FORM_MODEL
