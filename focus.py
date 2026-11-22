import curses
import functools
import json
import logging
import os
import plistlib
import signal
import subprocess
import sys
import time
from datetime import datetime
from getpass import getpass
from pathlib import Path

from busylib import BusyBar, BusyBarDevices
from busylib.exceptions import BusyBarAPIError, BusyBarError, BusyBarRequestError
from busylib.features.timer import timer_state
from zeroconf import InterfaceChoice, Zeroconf

APP = Path(__file__).resolve().parent
CONFIG = APP / "config.json"
LABEL = "app.busy.focus-mode"
DOMAIN = f"gui/{os.getuid()}"
PLIST = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
LOG = Path.home() / "Library/Logs/busybar-focus-mode.log"
SHORTCUTS = {True: "BUSY Focus On", False: "BUSY Focus Off"}
POLL_S = 3

logging.getLogger("busylib").disabled = True


@functools.cache
def bar(addr=None, token=None):
    return BusyBar(addr, token=token, max_retries=0, timeout=2)


def refused(error):
    return isinstance(error, BusyBarAPIError) and error.status_code in (401, 403)


def describe(error):
    if refused(error):
        return "refused"
    if isinstance(error, BusyBarAPIError):
        return f"HTTP {error.status_code}"
    if isinstance(error, BusyBarRequestError):
        return error.message
    return type(error).__name__


def clients(config, zc):
    devices = BusyBarDevices.discover(0.5, zeroconf=zc)
    device = next((d for d in devices if d.device_id == config.get("id")), None)
    if device:
        for affinity in ("over_usb",) if config.get("usb_only") else ("over_usb", "over_wifi"):
            if addr := device.get_address(affinity):
                yield addr, bar(addr, config.get("pin"))
    if config.get("cloud_token"):
        yield "cloud", bar(token=config["cloud_token"])


def wants_focus(snapshot):
    state = timer_state(snapshot)
    return state.is_running and not state.is_paused and state.phase != "rest"


def set_focus(on):
    subprocess.run(["/usr/bin/shortcuts", "run", SHORTCUTS[on]], check=True, timeout=30, capture_output=True)


def run():
    config = json.loads(CONFIG.read_text())
    zc = Zeroconf(InterfaceChoice.All)
    last = {}
    focus = None

    def log(topic, message=None):
        if message and last.get(topic) != message:
            print(datetime.now().isoformat(timespec="seconds"), message, flush=True)
        last[topic] = message

    def stop(*_):
        set_focus(False)
        sys.exit(0)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)
    snapshot = None
    while True:
        errors = []
        for route, client in clients(config, zc):
            try:
                snapshot = client.busy_snapshot()
                log("bar")
                break
            except BusyBarError as error:
                errors.append(f"{route}: {describe(error)}")
        else:
            log("bar", f"bar unreachable ({'; '.join(errors) or 'not found'})")
        if snapshot and (want := wants_focus(snapshot)) != focus:
            try:
                set_focus(want)
                focus = want
                log("focus")
            except (subprocess.SubprocessError, OSError) as error:
                log("focus", f"shortcut failed: {error}")
        time.sleep(POLL_S)


def accepted(client):
    try:
        client.busy_snapshot()
        return True
    except BusyBarError as error:
        if refused(error):
            return False
        raise


def choose(question, labels):
    def menu(screen):
        curses.curs_set(0)
        curses.use_default_colors()
        selected = 0
        while True:
            screen.erase()
            try:
                screen.addstr(0, 0, f"{question} Arrows to move, Return to pick.")
                for i, label in enumerate(labels):
                    screen.addstr(i + 2, 2, label, curses.A_REVERSE if i == selected else curses.A_NORMAL)
            except curses.error:
                pass
            key = screen.getch()
            if key == curses.KEY_UP:
                selected = (selected - 1) % len(labels)
            elif key == curses.KEY_DOWN:
                selected = (selected + 1) % len(labels)
            elif key in (curses.KEY_ENTER, 10, 13):
                return selected

    return curses.wrapper(menu)


def setup():
    if CONFIG.exists() and choose("Settings found.", ["Keep current settings", "Set up again"]) == 0:
        return
    config = {}
    devices = BusyBarDevices.discover(3)
    if devices:
        device = devices[0] if len(devices) == 1 else devices[
            choose("Which BUSY Bar?", [f"{d.name} ({d.device_id}, {d.get_address()})" for d in devices])
        ]
        config["id"] = device.device_id
        while not accepted(bar(device.get_address(), config.get("pin"))):
            config["pin"] = getpass("PIN: ").strip()
        if config.get("pin") and choose("Wi-Fi sends the PIN unencrypted. Use it anyway?", ["Yes", "No, USB and cloud only"]) == 1:
            config["usb_only"] = True
        print(f"✓ {device.name}")
    else:
        print("No bar found over USB or Wi-Fi.")

    if not devices or choose("Also connect through the BUSY cloud?", ["Yes", "No"]) == 0:
        while True:
            token = getpass("BUSY cloud token from https://cloud.busy.app/dashboard: ").strip()
            if not token:
                continue
            if accepted(bar(token=token)):
                break
            print("The cloud refused that token.")
        config["cloud_token"] = token
        config.setdefault("id", bar(token=token).status_device().usb_mac.replace(":", ""))
        print("✓ BUSY cloud")

    os.umask(0o077)
    CONFIG.write_text(json.dumps(config))


def start():
    while True:
        installed = subprocess.run(["/usr/bin/shortcuts", "list"], check=True, capture_output=True, text=True).stdout
        missing = [n for n in SHORTCUTS.values() if n not in installed.splitlines()]
        if not missing:
            break
        for name in missing:
            subprocess.run(["/usr/bin/open", APP / "shortcuts" / f"{name}.shortcut"], check=True)
        input(f"Click “Add Shortcut” for {' and '.join(missing)}, then press Return.")

    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(APP / "focus.py"), "run"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(LOG),
        "StandardErrorPath": str(LOG),
    }))
    launchctl("bootout", f"{DOMAIN}/{LABEL}")
    launchctl("bootstrap", DOMAIN, str(PLIST), check=True)
    print(f"✓ Running. Log: {LOG}")


def launchctl(*args, check=False):
    subprocess.run(["/bin/launchctl", *args], check=check, capture_output=True)


if __name__ == "__main__":
    commands = {"setup": setup, "start": start, "run": run}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(f"usage: {sys.argv[0]} {' | '.join(commands)}")
    try:
        commands[sys.argv[1]]()
    except BusyBarError as error:
        sys.exit(f"Can't reach the BUSY Bar: {describe(error)}")
    except KeyboardInterrupt:
        sys.exit(1)
