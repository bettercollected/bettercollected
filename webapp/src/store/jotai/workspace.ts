'use client';

import { atom, useAtom } from 'jotai';

export interface Workspace {
    id: string;
    title: string;
    workspaceName: string;
    description: string;
    ownerId: string;
    profileImage?: string;
    bannerImage?: string;
    customDomain?: string;
    dashboardAccess?: string;
    default?: string;
    disabled?: string;
    privacyPolicy?: string;
    termsOfService?: string;
    isPro?: boolean;
}

const workspaceAtom = atom<Workspace>({
    id: '',
    title: '',
    workspaceName: '',
    description: '',
    ownerId: ''
});

export default function useWorkspace() {
    const [workspace, setWorkspace] = useAtom(workspaceAtom);

    return {
        workspace,
        setWorkspace
    };
}
