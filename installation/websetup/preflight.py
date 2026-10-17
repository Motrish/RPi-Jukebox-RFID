"""Read-only, privacy-limited host observations for the local setup page."""
import platform
import re
import shutil
import stat
import struct
import sys
from pathlib import Path

_SCHEMA = "websetup.preflight.v1"
_OS_KEYS = ("NAME", "ID", "ID_LIKE", "VERSION_ID")
_MAX_OS_RELEASE = 4096
_MAX_MEMINFO = 65536


def parse_os_release(text):
    """Parse selected os-release assignments as data; never evaluate them."""
    if not isinstance(text, str):
        return {}
    result = {}
    for line in text[:_MAX_OS_RELEASE].splitlines():
        key, separator, value = line.partition("=")
        if not separator or key not in _OS_KEYS or key in result:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        value = value[:120]
        if value and all(char.isprintable() for char in value):
            result[key] = value
    return result


def _observed(value):
    return {"status": "observed", "value": value}


def _unknown(reason):
    return {"status": "unknown", "reason": reason}


def _read_os_release(path):
    with open(path, "r", encoding="utf-8", errors="replace") as source:
        return source.read(_MAX_OS_RELEASE + 1)


def _os_facts(reader):
    try:
        values = parse_os_release(reader())
    except (OSError, UnicodeError, ValueError):
        values = None
    facts = {}
    for key in _OS_KEYS:
        fact_key = "os_" + key.lower()
        if values is None:
            facts[fact_key] = _unknown("Die Betriebssystemdaten konnten nicht gelesen werden.")
        elif key in values:
            facts[fact_key] = _observed(values[key])
        else:
            facts[fact_key] = _unknown("Das Betriebssystemfeld %s ist nicht verfügbar." % key)
    return facts


def _system_probe():
    return {
        "machine": platform.machine() or None,
        "pointer_bits": struct.calcsize("P") * 8,
        "python": "%d.%d.%d" % sys.version_info[:3],
    }


def _system_facts(probe):
    try:
        values = probe() or {}
    except Exception:
        values = {}
    machine, bits = values.get("machine"), values.get("pointer_bits")
    if isinstance(machine, str) and machine and bits in (32, 64):
        architecture = _observed({"machine": machine[:40], "pointer_bits": bits})
    else:
        architecture = _unknown("Architektur oder Wortbreite konnte nicht ermittelt werden.")
    version = values.get("python")
    python_fact = _observed(str(version)[:20]) if version else _unknown("Die Python-Version konnte nicht ermittelt werden.")
    return architecture, python_fact


def _read_small(path, limit):
    with open(path, "r", encoding="ascii", errors="replace") as source:
        return source.read(limit)


def _mem_total(text):
    for line in text[:_MAX_MEMINFO].splitlines():
        match = re.fullmatch(r"MemTotal:\s*(\d+)\s*kB\s*", line)
        if match:
            return int(match.group(1)) * 1024
    return None


def _memory_fact(reader):
    try:
        value = _mem_total(reader("/proc/meminfo", _MAX_MEMINFO))
    except (OSError, UnicodeError, ValueError):
        value = None
    return _observed(value) if value is not None else _unknown("Der Arbeitsspeicher konnte nicht gelesen werden.")


def _disk_fact(probe, root):
    try:
        value = probe(root)
        value = int(value) if value is not None and int(value) >= 0 else None
    except (OSError, ValueError, TypeError):
        value = None
    return _observed(value) if value is not None else _unknown("Freier Speicherplatz konnte nicht ermittelt werden.")


def _file_marker(path):
    try:
        return stat.S_ISREG(path.stat().st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        return None


def _marker_fact(probe, path):
    try:
        present = probe(path)
    except Exception:
        present = None
    if present is None:
        return _unknown("Der Marker konnte nicht geprüft werden.")
    return _observed(bool(present))


def _settings_fact(probe, root):
    markers = {
        "jukebox_config": _marker_fact(probe, root / "shared/settings/jukebox.yaml"),
        "logger_config": _marker_fact(probe, root / "shared/settings/logger.yaml"),
    }
    values = {key: marker["value"] for key, marker in markers.items() if marker["status"] == "observed"}
    if len(values) == len(markers):
        return {"status": "observed", "value": values, "markers": markers}
    reason = "Mindestens ein Einstellungsmarker konnte nicht geprüft werden."
    return {
        "status": "unknown",
        "reason": reason,
        "markers": markers,
    }


def build_report(root=Path.cwd(), os_release_reader=None, system_probe=None,
                 file_reader=None, disk_probe=None, marker_probe=None):
    """Build observations. Probe callables are injectable for deterministic tests."""
    root = Path(root)
    os_release_reader = os_release_reader or (lambda: _read_os_release("/etc/os-release"))
    system_probe = system_probe or _system_probe
    file_reader = file_reader or _read_small
    disk_probe = disk_probe or (lambda path: shutil.disk_usage(path).free)
    marker_probe = marker_probe or _file_marker
    architecture, python_fact = _system_facts(system_probe)
    facts = _os_facts(os_release_reader)
    facts.update({
        "architecture": architecture,
        "python": python_fact,
        "memory": _memory_fact(file_reader),
        "free_disk": _disk_fact(disk_probe, root),
        "repository": _marker_fact(marker_probe, root / "installation/install-jukebox.sh"),
        "bundle": _marker_fact(marker_probe, root / "src/webapp/build/index.html"),
        "installation": {"settings": _settings_fact(marker_probe, root)},
    })
    return {
        "schema": _SCHEMA,
        "scope": "Nur beobachtete Fakten; dieser Bericht bestätigt weder Geräteunterstützung noch Einsatzbereitschaft.",
        "facts": facts,
    }
