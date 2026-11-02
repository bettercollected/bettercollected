# Embedding a form in your own website

A published form can be shown inside another website. The form stays on this server (the visitor's
answers are sent here, never to the page around it); your page only holds a frame and a small script that
keeps the frame as tall as the form's current page needs.

Embedding is behind the server setting `FORM_EMBED_ENABLED` (off by default). While it is off nothing below
exists: the settings answer 404, the Embed tab is hidden and form pages are served exactly as before.

## Quick start

1. Workspace settings, **Embedding**: add the address of the site that will show the form, for example
   `https://www.example.org` (see [Allowed sites](#allowed-sites)).
2. On the form's **Share** dialog open the **Embed** tab and copy the code:

```html
<div data-bc-form="https://forms.example.org/acme/forms/contact" data-bc-title="Contact form"></div>
<script async src="https://forms.example.org/embed/v1.js"
        integrity="sha384-IHR6t5d0yCNPCK4uaKckT/RXBuFfNSKj1x29Y1WV2d8FmZaGWF9q+5DupaXWAF+z"
        crossorigin="anonymous"></script>
```

3. Paste it where the form should appear. The form's address is the one you share as a link (the
   workspace's custom domain, when it has one, shows `https://forms.customer.example/forms/contact`); the
   script is always served by the same host as the form.

The script file `/embed/v1.js` **never changes** once released (a change is a new file, `v2.js`, and a new snippet),
so the tag pins it with `integrity` (Subresource Integrity) and `crossorigin="anonymous"`: if the file were ever
altered on its way or on the server, the browser would refuse to run it. The file is served with a year-long
immutable cache and `Access-Control-Allow-Origin: *`. `/embed.js` is a moving alias of the current version for
pages that do not pin it (no `integrity` there, cached for an hour).

### Without any script

If you would rather run no script of ours on your page, use a plain frame (the Embed tab shows this too):

```html
<iframe src="https://forms.example.org/acme/forms/contact?embed=1" title="Contact form"
        width="100%" height="640" style="border:0" loading="lazy" referrerpolicy="origin" allow=""></iframe>
```

The frame keeps the height you give it (set it to fit your form; pages differ), does not resize itself and tells
your page nothing (the page learns no `parent`). Sign-in and other links that leave the form still open in a new
tab (`embed=1`). The allowed-sites list applies exactly as for the script.

**`sandbox`.** A host that sandboxes frames must keep `allow-scripts allow-forms allow-same-origin allow-popups
allow-popups-to-escape-sandbox`: the form needs scripts, its own storage, the form submission and the new-tab
sign-in. Without `allow-same-origin` the frame runs as an opaque origin and the form cannot keep its state, and with
the script embed a message would come from the origin `null`, which the script refuses.

Any site that is not on the list is refused by the browser: the frame stays empty.

## Options

Set these as attributes on the placeholder element.

| Attribute | Meaning | Default |
|---|---|---|
| `data-bc-form` | The form's address. `https://` only (`http://` for `localhost`, `*.localhost` and `127.0.0.1`, to try it); no user name or fragment. | required |
| `data-bc-title` | The frame's accessible name. Screen readers announce it: use the form's title. | `Form` |
| `data-bc-min-height` | The height in pixels before the form has reported its own (240 to 4000). | `480` |
| `data-bc-lang` | `en` or `nl`. Without it the form uses the visitor's browser language, as a plain link does. | browser |
| `data-bc-theme` | `light`, `dark` or `auto`: the frame's colour scheme only, so a dark page does not flash white. The form keeps the colours its creator chose; respondent pages have no dark mode. | `auto` |

The address may carry the form's own query: hidden-field values (`?source=newsletter`) and prefilled
answers work as on a shared link.

## Size

The form is a one-page-at-a-time layout, so the frame has no single "document height". Inside the frame the
page measures itself (its content, the organisation strip and the privacy strip below it) and tells the
script the height it needs for the page on screen, between 240 and 4000 px. The script sets the frame to
that height, with a short transition that is skipped when the visitor prefers reduced motion. The privacy
panel starts closed inside a frame (an open panel would change the height back and forth).

## Events

The script dispatches DOM events on the placeholder element (they bubble) and calls handlers registered with
`BetterCollectedEmbed.on`. `detail` holds exactly the message's data:

| Event | `detail` | When |
|---|---|---|
| `bc-form:loaded` | `{ type: "loaded" }` | the form is on screen |
| `bc-form:height` | `{ type: "height", height }` | the page needs another height, in steps of 40 px (the script has already applied it) |
| `bc-form:submitted` | `{ type: "submitted" }` | the response was accepted |

```js
document.querySelector('[data-bc-form]').addEventListener('bc-form:submitted', () => {
    // thank the visitor, close a dialog, send your own analytics event ...
});
BetterCollectedEmbed.on('height', (detail, element) => { /* ... */ });
```

`BetterCollectedEmbed.scan(root)` mounts placeholders added later (single-page applications);
`BetterCollectedEmbed.version` is the protocol version (`1`). Loading the script twice is harmless.

### What your page learns, and what it does not

Exactly three things: that the form loaded, how tall the page on screen needs to be (in steps of 40 px) and that
the response was submitted. Never an answer, a field, the response's id, the form's title or any other text of the
form, and no page number or counter (with branching, the number of pages a respondent sees depends on their
answers). The height is the one value that still varies with the page shown, so on a form that branches it can
depend on earlier answers; use a form whose pages have the same height where that matters. The embedded form
shows its own privacy information and consent exactly as on a shared link.

The messages are sent only while the server has embedding switched on (`FORM_EMBED_ENABLED`). With the switch off a
form can still be framed by any site, as before the feature (see "Allowed sites"), but the framed page tells the
site around it nothing, even with `?embed=1&parent=...` in its address.

### React

```tsx
import { useEffect, useRef } from 'react';

export function BetterCollectedForm({ src, title, onSubmitted }: { src: string; title: string; onSubmitted?: () => void }) {
    const host = useRef<HTMLDivElement>(null);
    useEffect(() => {
        const element = host.current;
        if (!element) return;
        const script = document.createElement('script');
        script.async = true;
        script.src = `${new URL(src).origin}/embed/v1.js`;
        // pin it like the share dialog's snippet does: set script.integrity (the sha384 shown there) and
        // script.crossOrigin = 'anonymous'
        script.onload = () => window.BetterCollectedEmbed?.scan(element);
        // the script mounts the placeholder as soon as it runs; a second load only scans
        document.head.appendChild(script);
        const submitted = () => onSubmitted?.();
        element.addEventListener('bc-form:submitted', submitted);
        return () => {
            element.removeEventListener('bc-form:submitted', submitted);
            script.remove();
        };
    }, [src]);
    return <div ref={host} data-bc-form={src} data-bc-title={title} />;
}
```

This is documentation only for now; an npm package can follow if there is demand.

## Allowed sites

Workspace settings, **Embedding** (workspace owners and admins). The list is the form pages'
`Content-Security-Policy: frame-ancestors`: this site, the dashboard (its preview frames the form) and your
list. At most 20 entries.

- `https://www.example.org`: that site. A port is allowed (`https://example.org:8443`); the default port is
  dropped.
- `https://*.example.org`: every subdomain of a domain of your own. It does **not** cover `example.org`
  itself: add that too. A wildcard under a shared suffix (`https://*.com`, `https://*.co.uk`,
  `https://*.github.io`) is refused (checked against the Public Suffix List).
- `http://localhost` and `http://127.0.0.1` (any port) are accepted for trying it on your own computer. They let any
  application on a visitor's own machine frame the form, so leave them out of a production list.
- Nothing else: no path, query, user name, IP address, one-label host or other scheme.

`https://*.example.org` also trusts every subdomain that is later taken over or pointed at someone else, so list the
exact sites where that matters. A change applies within 30 seconds. With no site on the list the form can only be shown by this site and the
dashboard's preview. Custom domains behave the same: the policy is chosen from the workspace the custom
domain's verified edge assertion names, and a request without a valid assertion gets the strict default.

While `FORM_EMBED_ENABLED` is off no framing header is sent for form pages (as before this feature), so
a site that already frames a form keeps working until the switch is turned on. **Turning it on starts refusing every
site that is not listed**: tell the people who embed your forms to add their sites first.

The same holds while the webapp cannot tell what the server's switch is, so a rollout in either order changes
nothing for embeds that work today: a backend that does not know the route yet (404) counts as "off"; so does a
failing or unreachable backend when nothing has been learned about the workspace yet. After the backend has
answered, an outage keeps the last answer it gave (for up to ten minutes; then the strict default), so a blip
neither opens a workspace's forms to every site nor closes them to the sites it lists. Deploy the backend before
the webapp where you can.

**Tell the webapp as well.** One case needs the webapp's own knowledge: a freshly started webapp whose first
ask of the backend fails (the backend is down or restarting at that moment) and that has no earlier answer. With
the switch on that must not leave forms open to every site, so the webapp reads its own environment variable
`FORM_EMBED_ENABLED` (same name and values as the backend's, read on every request; the deployment compose file
passes it through, default `false`): `true` means "strict until the backend answers" (`frame-ancestors 'self'` and
the dashboard), anything else means no header. **Set it to `true` on the webapp when you turn the switch on in the
backend**, in the same step. If you forget, the only effect is the old behaviour (no header) during such a
start-up failure; it never changes what the backend says once it answers, which stays the truth per workspace.

### Things that silently stop it working

- The script trusts the origin of the form address you gave. If that address redirects to another origin (a
  moved domain), every message from the frame is ignored and the frame keeps its minimum height: use the final
  address.
- A host page with an opaque origin (a `file:` page, a sandboxed frame) cannot be named in `parent`, so the form
  sends it nothing and the frame does not resize.
- The script accepts `http` form addresses on `localhost`, `*.localhost` and `127.0.0.1` for local trials; the
  allowed-sites list accepts `http` for `localhost` and `127.0.0.1` only (a host page on `*.localhost` needs
  an entry for its exact `http://localhost` origin or an https site).

## Signing in, drafts and cookies

An anonymous respondent needs no cookie, so an anonymous form works in any browser. Third-party cookies are
not dependable (Safari and others block them), so everything that needs the respondent's session happens in
a **new tab**: the sign-in links, "Verify and start" on a form that requires a verified identity (the page
says so), "switch account" and the respondent's own submission pages. After signing in the form is completed
in that tab. A form that requires a verified identity is better shared as a link. A saved draft's mail link
opens the form on its own address, not in the frame.

## How it works (for reviewers and operators)

- The frame address is the form's address plus `embed=1`, `parent=<your page's origin>` and optionally
  `lang`. The embedded page only trusts `parent` as the one origin it posts to (never `*`), only when it
  really is in a frame, and registers no `message` listener: nothing your page sends can change it.
- The script accepts a message only from the frame it created **and** from the form address's own origin, only
  with `source: "bettercollected-form"` and `v: 1`, and only a known type with a known shape (unknown keys are
  dropped, heights are clamped).
- The webapp's proxy sets `Content-Security-Policy: frame-ancestors ...` on `/<workspace>/forms/<form>` (and
  its `/preview`) and `/forms/<form>` on custom domains from `GET /workspaces/embed/policy` (public: it answers
  only what the header itself shows; unknown workspaces get an empty list; limited to 600 requests a minute per
  client address and 120 per workspace, then 429 with `Retry-After`, which the webapp treats like any failure). The answer is kept 30 s per workspace
  (one request at a time, at most 500 workspaces remembered). If the backend cannot be asked, the last answer is
  kept (see above); the strict default is used when a workspace had the switch on and its answer is ten minutes
  old, and for a custom-domain request whose edge assertion fails, never an open header.
- Every other page carries `frame-ancestors 'self' <dashboard origin>` (see "Who may frame a page" in the developers guide).
- API: `GET`/`PUT /workspaces/{id}/embed/settings` (`form.share` or `workspace.manage` reads, `workspace.manage`
  writes; 404 while the switch is off). No migration: the list is a field of the workspace record.
