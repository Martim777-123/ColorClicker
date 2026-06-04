# ColorClicker

A fast, lightweight desktop auto-clicker that detects and clicks specific colors on your screen — no scripting knowledge needed.

---

## What it does

ColorClicker scans a region of your screen and automatically clicks anywhere it finds a color that matches your target. You pick the color, draw the region, set the speed, and let it run.

It's built for situations where you need to click something that appears at a specific color — repeatedly, quickly, and accurately.

---

## Features

- **Region selector** — drag to define exactly which part of the screen to scan
- **Color picker** — pick colors from a wheel or directly from your screen with one click
- **Multi-color support** — add multiple target colors to the list
- **Color tolerance** — control how strict the match needs to be
- **Click interval** — set the speed, with optional human-like randomization
- **Multi-click points** — click multiple spread-out spots on a large object per pass
- **Click jitter** — nudges the mouse slightly before clicking to look more natural
- **Click offset randomization** — shifts each click by a random amount of pixels
- **Click mode** — left click, right click, or both
- **Click limit** — auto-stop after a set number of clicks
- **Excluded colors** — define colors to never click even if they match
- **Multiple scan regions** — scan more than one area of the screen per pass
- **Profile system** — save and load full configurations by name
- **Live HUD overlay** — small always-on-top status panel showing click count and scan speed
- **Single hotkey** — one key to start and stop (default F6, customizable)
- **Sound feedback** — plays a tone when starting and stopping
- **Settings panel** — toggle sound, overlay, region highlight, and change your hotkey

---

## How to use

1. Open `ColorClicker.exe`
2. Click **Select** to draw your scan region on screen
3. Click **Color Wheel** or **Pick from Screen** to add a target color
4. Adjust your settings (interval, tolerance, click mode, etc.)
5. Click **Start** or press **F6**
6. The app minimizes — it's now running
7. Press **F6** again or reopen the app and click **Stop** to stop it

---

## Requirements

Just the `.exe` — no Python or installs needed.

Windows only.

---

## Download

Head to the [Releases](../../releases) page and download the latest `ColorClicker.zip`.

Extract it and run `ColorClicker.exe`. That's it.

---

## Built with

- Python 3.14
- tkinter
- pynput
- mss
- Pillow
- PyInstaller

---

## Support

This took a genuinely long time to build. If you find it useful and want to show some appreciation, Consider buying me a coffee — It means a lot.

**PayPal:** paypal.me/MartimCunha811  
Or send to **@MartimCunha811** on PayPal

no pressure at all, just happy if it's useful to you.
## License

MIT — see `LICENSE` for details.
