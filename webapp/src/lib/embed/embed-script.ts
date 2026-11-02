/**
 * The embed script as the share dialog's snippet pins it (docs/embed.md): a versioned file that never changes
 * once released, served with a year-long immutable cache and `Access-Control-Allow-Origin: *`, so the snippet
 * can carry `integrity` (Subresource Integrity) and `crossorigin="anonymous"`. A change to the script is a new
 * file (`v2.js`) and a new entry here, never an edit of this one: `embed-script.test.ts` recomputes the hash of
 * every file in `public/embed/` and fails on a change.
 *
 * To add a version: put the file in `public/embed/`, print its hash with
 *   openssl dgst -sha384 -binary public/embed/vN.js | openssl base64 -A
 * and add it below.
 */
export const EMBED_SCRIPTS = {
    v1: { path: '/embed/v1.js', integrity: 'sha384-IHR6t5d0yCNPCK4uaKckT/RXBuFfNSKj1x29Y1WV2d8FmZaGWF9q+5DupaXWAF+z' }
} as const;

/** The version the snippets use. */
export const CURRENT_EMBED_SCRIPT = EMBED_SCRIPTS.v1;
