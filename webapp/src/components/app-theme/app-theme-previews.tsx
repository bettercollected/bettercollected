import React from 'react';

import type { AppTheme } from '@app/lib/app-theme';

// Small static pictures of the two app themes for the Appearance card: a page ground, a white card with a title and
// two lines of text, a button, and a row of form tiles. They are drawings, not the theme: the colours are written
// out here (a picture of Daybreak must stay Daybreak whichever theme the page around it wears) and decorative, so they
// are hidden from assistive technology; the option's name and description say what it is. Each colour is a role of
// the theme's block in tailwind.css, and `assets/css/app-theme.test.ts` compares them with it, so a changed token
// fails there until the picture follows.
export const THEME_PICTURES: Record<AppTheme, { ground: string; card: string; edge: string; ink: string; line: string; action: string; tiles: string[] }> = {
    // canvas, surface, hairline-strong, ink, hairline, app-action, form-hue-0..4-bg
    daybreak: { ground: '#F3F6FF', card: '#FFFFFF', edge: '#BDC8E8', ink: '#0E1737', line: '#DCE2F5', action: '#1649E2', tiles: ['#D4EFF0', '#FFF1C7', '#F3E8D8', '#E0E8FF', '#EEE8FC'] },
    pigment: { ground: '#FBF7F1', card: '#FFFFFF', edge: '#CFC4B1', ink: '#1A1238', line: '#E9E1D4', action: '#4B35DB', tiles: ['#FF8A73', '#FFC62E', '#5FD9B0', '#6BBEF7', '#D9A0FF'] }
};

export function AppThemePreview({ theme, className }: { theme: AppTheme; className?: string }) {
    const p = THEME_PICTURES[theme];
    return (
        <svg viewBox="0 0 160 90" role="presentation" aria-hidden="true" focusable="false" className={className} data-preview={theme}>
            <rect width="160" height="90" fill={p.ground} />
            <rect x="10" y="10" width="140" height="70" rx="6" fill={p.card} stroke={p.edge} />
            <rect x="20" y="20" width="46" height="6" rx="3" fill={p.ink} />
            <rect x="20" y="32" width="76" height="4" rx="2" fill={p.line} />
            <rect x="20" y="40" width="60" height="4" rx="2" fill={p.line} />
            <rect x="112" y="19" width="28" height="10" rx="3" fill={p.action} />
            {p.tiles.map((fill, index) => (
                <rect key={index} x={20 + index * 22} y="54" width="16" height="16" rx="4" fill={fill} />
            ))}
        </svg>
    );
}
