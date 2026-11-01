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
<script async src="https://forms.example.org/embed.js"></script>
```

3. Paste it where the form should appear. The form's address is the one you share as a link (the
   workspace's custom domain, when it has one, shows `https://forms.customer.example/forms/contact`); the
   script is always served by the same host as the form.

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
| `bc-form:height` | `{ type: "height", height }` | the page needs another height (the script has already applied it) |
| `bc-form:page` | `{ type: "page", kind, step, total }` | the respondent moved to another page. `kind` is `welcome`, `question`, `review` or `ending`; `step` counts the pages passed on this path; `total` is the form's number of pages |
| `bc-form:submitted` | `{ type: "submitted" }` | the response was accepted |

```js
document.querySelector('[data-bc-form]').addEventListener('bc-form:submitted', () => {
    // thank the visitor, close a dialog, send your own analytics event ...
});
BetterCollectedEmbed.on('page', (detail, element) => { /* ... */ });
```

`BetterCollectedEmbed.scan(root)` mounts placeholders added later (single-page applications);
`BetterCollectedEmbed.version` is the protocol version (`1`). Loading the script twice is harmless.

### What your page does not learn

Never an answer, a field, the response's id, the form's title or any other text of the form. `step` is a
counter, not a page number: with branching, a page number could reveal an answer. The embedded form shows its
own privacy information and consent exactly as on a shared link, and nothing the visitor does in it is
visible to your page beyond the table above.

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
        script.src = `${new URL(src).origin}/embed.js`;
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
- `http://localhost` and `http://127.0.0.1` (any port) are accepted for trying it on your own computer.
- Nothing else: no path, query, user name, IP address, one-label host or other scheme.

A change applies within 30 seconds. With no site on the list the form can only be shown by this site and the
dashboard's preview. Custom domains behave the same: the policy is chosen from the workspace the custom
domain's verified edge assertion names, and a request without a valid assertion gets the strict default.

While `FORM_EMBED_ENABLED` is off no framing header is sent for form pages (as before this feature), so
a site that already frames a form keeps working until the switch is turned on. **Turning it on starts refusing every
site that is not listed**: tell the people who embed your forms to add their sites first.

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
  only what the header itself shows; unknown workspaces get an empty list). If the backend cannot be asked the
  header is the strict default, never an open one.
- The dashboard pages now carry `frame-ancestors 'self'`.
- API: `GET`/`PUT /workspaces/{id}/embed/settings` (`form.share` or `workspace.manage` reads, `workspace.manage`
  writes; 404 while the switch is off). No migration: the list is a field of the workspace record.
