import React from 'react';

import MarkdownText from '@app/components/ui/markdown-text';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface WorkspaceHeaderProps {
    workspace: WorkspaceDto;
}

export default function WorkspaceHeader({ workspace }: WorkspaceHeaderProps) {
    return (
        <div className="h-full w-full ml-0 md:ml-10">
            <div className="w-full md:w-9/12">
                <h1 className="font-semibold text-darkGrey text-xl sm:text-2xl md:text-3xl xl:text-4xl">{workspace.title}</h1>
                <MarkdownText description={workspace.description} contentStripLength={300} markdownClassName="pt-3 md:pt-7 text-base text-grey" textClassName="text-base" />
            </div>
        </div>
    );
}
