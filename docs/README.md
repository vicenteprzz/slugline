# Slugline's website

`index.html` is the public page: what Slugline does, prices and the download.
It is a single static page with its images in `img/`, so GitHub Pages can host
it for free.

## Before publishing

At the top of `index.html`, fill in:

```js
window.SLUGLINE = { contact: "", download: "", buy: "" };
```

- `contact`: the email where demo requests and purchases should go.
- `download`: a link to `Slugline.dmg` (see below).
- `buy`: a payment link, if you have one. Without it, "Comprar" opens an email.

Until they're filled in, those buttons show dimmed. Check the prices in the
Precios section too.

## Publishing the page (GitHub Pages)

1. Merge this folder into `main` and push it.
2. On GitHub: **Settings → Pages → Build and deployment → Deploy from a branch**,
   branch `main`, folder `/docs`, **Save**.
3. A minute later the page is at `https://<your-user>.github.io/slugline/`.
   A custom domain (`slugline.app` or similar) can be set on the same screen.

## Publishing the download

1. Build the app: `packaging/macos/build.sh` (it makes `dist/Slugline.dmg`).
2. On GitHub: **Releases → Draft a new release**, tag `v0.7.0`, and drag
   `Slugline.dmg` into the assets box. Publish it.
3. Copy the link of the uploaded `.dmg` and paste it as `download` above.

The app is not signed yet, so on other Macs the first launch needs a right
click → **Open**. An Apple Developer ID (99 $/year) removes that warning.

## Updating the screenshots

The images in `img/` are screenshots of the real app (light and dark), taken
with John's Boys open and a hand-made breakdown and schedule; none of them
shows AI output. Retake them after visible changes to the app.
