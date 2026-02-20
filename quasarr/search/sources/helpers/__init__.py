import os
import pkgutil


def get_hostnames():
    hostnames = []

    for _, module_name, _ in pkgutil.iter_modules([os.path.dirname(__path__[0])]):
        if module_name == "abstract" or module_name == "helpers":
            continue

        hostnames.append(module_name)
    return hostnames


def get_login_required_hostnames():
    from quasarr.search.sources import get_sources

    return [
        source.initials for source in get_sources().values() if source.requires_login
    ]
