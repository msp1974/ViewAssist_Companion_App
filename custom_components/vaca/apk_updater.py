"""Keep the newest VACA APK from GitHub releases staged for devices without internet.

The app resolves its updates the same way: GET /releases/latest on the GitHub API and take the
asset with the Android package content type. The file is saved as vaca-<version>.apk in the apk
folder, which the existing /vaca static path serves and get_staged_apk advertises to satellites.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from pathlib import Path
import re
import shutil
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started

from .const import APK_PATH, CUSTOM_PATH, DOMAIN
from .custom import get_staged_apk

_LOGGER = logging.getLogger(__name__)

GITHUB_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/msp1974/ViewAssist_Companion_App/releases/latest"
)
APK_CONTENT_TYPE = "application/vnd.android.package-archive"
CHECK_INTERVAL = timedelta(hours=12)

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")
# Files this module writes. Differently named (manually staged) files are never pruned.
_DOWNLOADED_APK_RE = re.compile(r"^vaca-(\d+)\.(\d+)\.(\d+)\.apk$")


def _parse_version(value: str) -> tuple[int, int, int] | None:
    """Parse v1.2.3 / 1.2.3 into a comparable tuple."""
    if match := _VERSION_RE.match(value or ""):
        return tuple(int(p) for p in match.groups())  # type: ignore[return-value]
    return None


def pick_release_apk(release: dict[str, Any]) -> tuple[str, str, int] | None:
    """Return (version, download_url, size) of the APK asset of a GitHub release."""
    if release.get("draft") or release.get("prerelease"):
        return None
    version = _parse_version(release.get("tag_name") or release.get("name") or "")
    if version is None:
        return None
    for asset in release.get("assets") or []:
        if asset.get("content_type") == APK_CONTENT_TYPE and asset.get(
            "browser_download_url"
        ):
            return (
                ".".join(map(str, version)),
                asset["browser_download_url"],
                int(asset.get("size") or 0),
            )
    return None


def _prune_older(apk_dir: Path, keep: str) -> None:
    """Remove older vaca-<version>.apk files so releases do not pile up."""
    keep_version = _parse_version(keep)
    for file in apk_dir.iterdir():
        match = _DOWNLOADED_APK_RE.match(file.name)
        if match and tuple(int(p) for p in match.groups()) < keep_version:
            file.unlink(missing_ok=True)
            _LOGGER.debug("Removed old staged APK %s", file.name)


async def async_download_latest_apk(hass: HomeAssistant) -> None:
    """Download the latest GitHub release APK unless a same or newer one is staged."""
    session = async_get_clientsession(hass)
    async with session.get(
        GITHUB_LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json"},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as response:
        response.raise_for_status()
        release = await response.json()

    if (picked := pick_release_apk(release)) is None:
        _LOGGER.debug("Latest VACA release has no APK to stage")
        return
    version, url, size = picked

    staged = await hass.async_add_executor_job(get_staged_apk, hass)
    if staged and _parse_version(staged[0]) >= _parse_version(version):
        _LOGGER.debug("VACA %s or newer already staged (%s)", version, staged[1])
        return

    apk_dir = Path(hass.config.path(DOMAIN), CUSTOM_PATH, APK_PATH)
    target = apk_dir / f"vaca-{version}.apk"
    part = apk_dir / f"{target.name}.part"
    _LOGGER.info("Downloading VACA %s from GitHub to %s", version, target)

    def _open() -> Any:
        apk_dir.mkdir(parents=True, exist_ok=True)
        if (free := shutil.disk_usage(apk_dir).free) < size * 1.1:
            raise OSError(
                f"not enough disk space for VACA {version}: "
                f"{free // 2**20} MB free, {size // 2**20} MB needed"
            )
        return part.open("wb")

    def _discard() -> None:
        part.unlink(missing_ok=True)

    handle = await hass.async_add_executor_job(_open)
    written = 0
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=None, sock_read=60)
        ) as response:
            response.raise_for_status()
            async for chunk in response.content.iter_chunked(1 << 20):
                await hass.async_add_executor_job(handle.write, chunk)
                written += len(chunk)
        if size and written != size:
            raise OSError(f"incomplete download: {written} of {size} bytes")
    except BaseException:
        # includes cancellation on shutdown: never leave a partial file behind
        await hass.async_add_executor_job(handle.close)
        await hass.async_add_executor_job(_discard)
        raise
    await hass.async_add_executor_job(handle.close)

    def _finish() -> None:
        part.replace(target)
        _prune_older(apk_dir, version)

    await hass.async_add_executor_job(_finish)
    _LOGGER.info("VACA %s staged, satellites will offer it as an update", version)


def async_setup_apk_updates(hass: HomeAssistant) -> None:
    """Check GitHub for a new VACA release once started and then every 12 hours."""
    lock = asyncio.Lock()
    warned = False

    async def _check() -> None:
        nonlocal warned
        if lock.locked():
            return
        async with lock:
            try:
                await async_download_latest_apk(hass)
                warned = False
            except (aiohttp.ClientError, TimeoutError, OSError, ValueError) as err:
                # HA itself may be offline too: warn once, then keep quiet until it recovers
                (_LOGGER.debug if warned else _LOGGER.warning)(
                    "Could not fetch the latest VACA release from GitHub: %s", err
                )
                warned = True

    @callback
    def _run(_: datetime | None = None) -> None:
        hass.async_create_background_task(_check(), f"{DOMAIN}_apk_update_check")

    @callback
    def _started(_: HomeAssistant) -> None:
        _run()
        async_track_time_interval(hass, _run, CHECK_INTERVAL, cancel_on_shutdown=True)

    async_at_started(hass, _started)
