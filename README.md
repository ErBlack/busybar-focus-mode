# BUSY Bar Focus Mode

While a [BUSY Bar](https://busy.app) timer runs, the Mac is in the **Work** Focus. Pause, break or stop turns it off.

Reaches the bar over USB, then Wi-Fi, then the BUSY cloud if you add a token from [cloud.busy.app](https://cloud.busy.app/dashboard).

Built on [busylib](https://github.com/busy-app/busylib-py).

## Install

```
curl -fsSL https://raw.githubusercontent.com/ErBlack/busybar-focus-mode/main/install.sh | bash
```

Run it again to update, repair or change settings.

## Remove

```
curl -fsSL https://raw.githubusercontent.com/ErBlack/busybar-focus-mode/main/uninstall.sh | bash
```

## Debug

- Log: `~/Library/Logs/busybar-focus-mode.log`
- Local start: `./dev.sh` runs it from the checkout in the foreground
