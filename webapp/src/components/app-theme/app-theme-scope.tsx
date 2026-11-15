'use client';

import React from 'react';

import { asAppTheme } from '@app/lib/app-theme';
import { AppThemeContext } from '@app/lib/app-theme-context';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

/**
 * The workspace's app theme on the page (tailwind.css, "App theme scope"; DESIGN.md §1). It wraps the workspace
 * layout, inside the admin portal's own Daybreak scope, so the variables of a theme that has no block yet are still
 * Daybreak's (a custom property is inherited), and a theme with a block overrides them.
 *
 * `initial` is what the server read for this request (the member answer of `GET /workspaces`), so the first HTML the
 * server sends already carries the right value: nothing is read from a cookie or the browser's storage and no script
 * runs, hence no frame in the wrong theme. Once the workspace is in the store (it is a moment after the page loads),
 * the store's value wins, so a change in the Appearance card shows at once, without a reload. Anything but `pigment`
 * is `daybreak`. Only the workspace layout uses this: respondent routes never carry a theme attribute.
 */
export default function AppThemeScope({ workspaceId, initial, children }: { workspaceId: string; initial?: unknown; children: React.ReactNode }) {
    const workspace = useAppSelector(selectWorkspace);
    const fromStore = workspace?.id === workspaceId && workspace.appTheme !== undefined;
    const theme = asAppTheme(fromStore ? workspace.appTheme : initial);
    return (
        <div data-app-theme={theme} style={{ display: 'contents' }}>
            <AppThemeContext.Provider value={theme}>{children}</AppThemeContext.Provider>
        </div>
    );
}
