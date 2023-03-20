import React from 'react';

import MarkdownText from '@app/components/ui/markdown-text';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface WorkspaceHeaderProps {
    workspace: WorkspaceDto;
}

export default function WorkspaceHeader({ workspace }: WorkspaceHeaderProps) {
    return (
        <div className="h-full w-full ">
            <div className="py-4 md:py-6 xl:py-8 2xl:py-12 w-full md:w-9/12 xl:w-4/6 2xl:w-3/6">
                <h1 className="font-semibold text-darkGrey text-xl sm:text-2xl md:text-3xl xl:text-4xl 2xl:text-[40px]">{workspace.title}</h1>
                <MarkdownText description={workspace.description} contentStripLength={1000} markdownClassName="pt-3 md:pt-7 text-base text-grey" textClassName="text-base" />
            </div>
        </div>
    );
}
