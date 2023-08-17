import whois
from loguru import logger


def is_domain_available(domain: str):
    try:
        get_domain_info = whois.whois(domain)
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
