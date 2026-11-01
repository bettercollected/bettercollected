"""Countries an ``address`` question can take: ISO 3166-1 alpha-2 codes.

An address answer carries its country as one of these codes (``NL``). ``docs/spec/countries-v1.json`` is the copy the tests compare with; the
webapp's list (``webapp/src/utils/countries.ts``, with the webapp change) is
compared with it too. Names are
not kept here: a browser writes them in the respondent's language
(``Intl.DisplayNames``), and the server only ever needs the code.
"""

import re
from typing import Any

DEFAULT_COUNTRY = "NL"
# The most countries one question can allow.
COUNTRIES_MAX = 30

COUNTRY_CODES = frozenset(
    """
    AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM
    BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX
    CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG
    GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR
    IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV
    LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE
    NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO
    RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF
    TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF
    WS YE YT ZA ZM ZW
    """.split()
)

_CODE = re.compile(r"^[A-Z]{2}$")


def is_country_code(value: Any) -> bool:
    """Is ``value`` one of the ISO 3166-1 alpha-2 codes above (upper case)?"""
    return isinstance(value, str) and _CODE.fullmatch(value) is not None and value in COUNTRY_CODES
