'use client';

import { atom, useAtom } from 'jotai';

// The Public Workspace mirror shows workspace settings inside its browser
// frame. This flag lets the sidebar "Workspace settings" item request that
// view before (or after) navigating to the dashboard root.
const workspaceSettingsViewAtom = atom(false);

export function useWorkspaceSettingsView() {
    const [settingsViewOpen, setSettingsViewOpen] = useAtom(workspaceSettingsViewAtom);
    return { settingsViewOpen, setSettingsViewOpen };
}
