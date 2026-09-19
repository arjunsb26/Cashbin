# Phone page

The camera page. Plain HTML, CSS and JavaScript, no build step and no dependencies in
what the phone downloads. The backend serves this folder at `/phone` over HTTPS. Lane E
owns this directory.

```
index.html            the page
phone.css             tokens and layout
phone.js              camera, streaming, socket, sheets
manifest.webmanifest  add to home screen
fonts/                IBM Plex Sans and Sans Condensed, woff2, OFL licence beside them
icons/                home screen icons, drawn by dev/make_icons.py
dev/                  the mock backend and the screenshot run. Never served to a phone.
```

## Run the mock backend

From the worktree root:

```
uv run --project backend python phone/dev/mock_server.py
```

It makes its own certificate in `phone/dev/certs/` on first run, with `localhost` and
this laptop's LAN addresses in it, then prints one URL per address. Flags:

```
--port 8443     the port to bind
--host 0.0.0.0  the interface to bind
--no-script     do not play the scripted result and ask
```

With the script on, five seconds after the first camera frame it sends a result, eight
seconds after that an ask, and an idle once an answer is posted.

## Open it on a phone

1. Put the phone and the laptop on the same network. A phone hotspot works and is
   usually faster than venue wifi.
2. Open the `https://<laptop address>:8443/phone/` line the mock printed.
3. The browser warns about the certificate. Accept it once. On iOS Safari tap Show
   details, then Visit this website. On Android Chrome tap Advanced, then Proceed.
4. Tap Start camera and allow the camera. Frames start at once and the mock logs how
   many it receives each second.

The camera needs HTTPS. Over plain HTTP the page says so and keeps the camera off.

## Add it to the home screen

- iOS Safari: Share, then Add to Home Screen. It opens with no browser chrome.
- Android Chrome: the three dot menu, then Add to Home screen or Install app.

The installed name comes from `manifest.webmanifest`, which a browser reads before any
script runs. There is no build step here, so that name is the fallback name, not the
product name from `brand.json`. The page title and the name on the first screen are
replaced from `brand.json` as soon as it loads.

## Screenshots

With the mock running:

```
cd phone/dev
pnpm install
pnpm exec playwright install chromium
pnpm screenshots
```

Chromium runs at 390x844 with a fake camera and writes to `phone/dev/screenshots/`.
Pass `--base=https://localhost:8443` or `--out=<folder>` to change either.
