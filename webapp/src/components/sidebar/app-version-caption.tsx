import React from 'react';

/**
 * The version this build is, as a quiet caption under the dashboard sidebar's
 * attribution. It is a build fact: CI passes NEXT_PUBLIC_APP_VERSION as a
 * Docker build argument (.github/workflows/deploy.yml) and `next build` inlines
 * it here; self-built images take it from scripts/app-version.sh.
 *
 * Accepted values (anything else shows nothing, so a stray value never looks
 * like a release):
 * - `v4.0.2` or `v4.1.0-rc.1`: a release tag, shown as is
 * - `dev-<sha>` / `staging-<sha>`: the develop / master stacks, shown as `dev · b3a8cee`
 * - `<sha>`: a self-built image off a tag, shown as `build · b3a8cee`
 *
 * Only the dashboard sidebar renders this module: respondent pages (forms,
 * the responder portal, submissions) never show the version.
 */

const RELEASE = /^v(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)$/;
const CHANNEL = /^(dev|staging)-([0-9a-f]{7,40})$/;
const COMMIT = /^([0-9a-f]{7,40})$/;

export interface AppVersionText {
    /** What the caption shows, e.g. `v4.0.2` or `dev · b3a8cee`. */
    visible: string;
    /** What follows "Version" for a screen reader, e.g. `4.0.2` or `dev b3a8cee`. */
    spoken: string;
}

export function describeAppVersion(raw: string | undefined | null): AppVersionText | null {
    const value = (raw ?? '').trim();
    if (!value) return null;
    const release = RELEASE.exec(value);
    if (release) return { visible: value, spoken: release[1] };
    const channel = CHANNEL.exec(value);
    if (channel) {
        const sha = channel[2].slice(0, 7);
        return { visible: `${channel[1]} · ${sha}`, spoken: `${channel[1]} ${sha}` };
    }
    const commit = COMMIT.exec(value);
    if (commit) {
        const sha = commit[1].slice(0, 7);
        return { visible: `build · ${sha}`, spoken: `build ${sha}` };
    }
    return null;
}

interface AppVersionCaptionProps {
    /** The build's version; defaults to the value inlined at build time. */
    version?: string;
    /** The visually hidden word read before the version ("Version"). */
    label?: string;
}

export default function AppVersionCaption({ version = process.env.NEXT_PUBLIC_APP_VERSION, label = 'Version' }: AppVersionCaptionProps) {
    const text = describeAppVersion(version);
    if (!text) return null;
    return (
        <p className="mt-1 px-4 text-center text-xs text-black-600" data-testid="app-version">
            <span className="sr-only">{`${label} ${text.spoken}`}</span>
            <span aria-hidden="true">{text.visible}</span>
        </p>
    );
}
