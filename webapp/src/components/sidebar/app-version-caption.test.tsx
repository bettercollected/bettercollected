import React from 'react';

import fs from 'fs';
import path from 'path';

import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import AppVersionCaption, { describeAppVersion } from './app-version-caption';

describe('describeAppVersion', () => {
    it('shows a release tag as is and speaks the number', () => {
        expect(describeAppVersion('v4.0.2')).toEqual({ visible: 'v4.0.2', spoken: '4.0.2' });
        expect(describeAppVersion('v4.1.0-rc.1')).toEqual({ visible: 'v4.1.0-rc.1', spoken: '4.1.0-rc.1' });
    });

    it('shows the dev and staging stacks with a short commit', () => {
        expect(describeAppVersion('dev-b3a8cee0e1234567')).toEqual({ visible: 'dev · b3a8cee', spoken: 'dev b3a8cee' });
        expect(describeAppVersion('staging-b3a8cee')).toEqual({ visible: 'staging · b3a8cee', spoken: 'staging b3a8cee' });
    });

    it('shows a self-built image off a tag as a build, never as a release', () => {
        expect(describeAppVersion('b3a8cee')).toEqual({ visible: 'build · b3a8cee', spoken: 'build b3a8cee' });
    });

    it('shows nothing for an empty or unexpected value', () => {
        for (const value of [undefined, null, '', '   ', 'latest', '4.0.2', 'v4', 'v4.0.2; rm', 'prod-b3a8cee', 'dev-xyz', '<b>v4.0.2</b>']) {
            expect(describeAppVersion(value)).toBeNull();
        }
    });
});

describe('AppVersionCaption', () => {
    afterEach(() => vi.unstubAllEnvs());

    it('renders the given release, read as "Version 4.0.2"', () => {
        render(<AppVersionCaption version="v4.0.2" />);
        const caption = screen.getByTestId('app-version');
        expect(caption.tagName).toBe('P');
        expect(caption).toHaveClass('text-black-600', 'text-xs', 'text-center');
        expect(caption.querySelector('a')).toBeNull();
        expect(screen.getByText('Version 4.0.2')).toHaveClass('sr-only');
        expect(screen.getByText('v4.0.2')).toHaveAttribute('aria-hidden', 'true');
        // a caption, not an announcement or a landmark
        expect(caption.closest('[aria-live]')).toBeNull();
        expect(caption.getAttribute('role')).toBeNull();
    });

    it('renders a non-release build in its short form, with a translated label', () => {
        render(<AppVersionCaption version="dev-b3a8cee" label="Versie" />);
        expect(screen.getByText('dev · b3a8cee')).toBeInTheDocument();
        expect(screen.getByText('Versie dev b3a8cee')).toHaveClass('sr-only');
    });

    it('renders nothing when the value is empty', () => {
        const { container } = render(<AppVersionCaption version="" />);
        expect(container).toBeEmptyDOMElement();
    });

    it('reads the build-time value by default, and nothing without one', () => {
        vi.stubEnv('NEXT_PUBLIC_APP_VERSION', 'staging-0123abc');
        const { unmount } = render(<AppVersionCaption />);
        expect(screen.getByText('staging · 0123abc')).toBeInTheDocument();
        unmount();

        vi.stubEnv('NEXT_PUBLIC_APP_VERSION', '');
        const { container } = render(<AppVersionCaption />);
        expect(container).toBeEmptyDOMElement();
    });
});

/**
 * The version is for the signed-in team only. These checks keep it out of
 * every respondent page: one module reads the build value, only the dashboard
 * sidebar renders that module, and only the admin portal's dashboard layout
 * renders the sidebar. (respondent-axe.test.tsx renders the respondent pages
 * with a value set and finds none.)
 */
describe('the version stays in the dashboard sidebar', () => {
    const SRC = path.resolve(__dirname, '../..');
    const sourceFiles = (dir: string): string[] =>
        fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
            const full = path.join(dir, entry.name);
            if (entry.isDirectory()) return sourceFiles(full);
            return /\.(ts|tsx|js|jsx)$/.test(entry.name) && !/\.(test|spec)\.[jt]sx?$/.test(entry.name) ? [full] : [];
        });
    const files = sourceFiles(SRC);
    const rel = (file: string) => path.relative(SRC, file).split(path.sep).join('/');
    const referencing = (pattern: RegExp) => files.filter((file) => pattern.test(fs.readFileSync(file, 'utf8'))).map(rel);

    it('only the caption reads the build value', () => {
        expect(referencing(/NEXT_PUBLIC_APP_VERSION/)).toEqual(['components/sidebar/app-version-caption.tsx']);
    });

    it('only the dashboard sidebar renders the caption', () => {
        expect(referencing(/sidebar\/app-version-caption['"]/)).toEqual(['components/sidebar/dashboard-drawer.tsx']);
    });

    it('only the admin portal renders the dashboard sidebar', () => {
        const importers = referencing(/sidebar\/dashboard-drawer['"]/);
        expect(importers.length).toBeGreaterThan(0);
        for (const file of importers) expect(file.startsWith('app/(admin-portal)/')).toBe(true);
    });
});
