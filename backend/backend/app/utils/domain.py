import re

import whois
from loguru import logger


def is_domain_available(domain: str):
    try:
        rec = re.compile(r"https?://(www\.)?")
        stripped_domain = rec.sub("", domain).strip().strip("/")
        get_domain_info = whois.whois(stripped_domain)
        if (
            get_domain_info
            and get_domain_info.text
            and get_domain_info.text.__contains__("Domain not found.")
        ):
            return True
        logger.warning(f"Domain exists: {domain}")
        return False
    except Exception:
        return True
