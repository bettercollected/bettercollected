import React from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import MarkdownText from '@Components/Common/Markdown';

import { useAppSelector } from '@app/store/hooks';
import { toEndDottedStr, trimTooltipTitle } from '@app/utils/stringUtils';


interface IPublicWorkspaceTitleAndDescriptionProps {
    isFormCreator: boolean;
    className?: string;
}

export default function PublicWorkspaceTitleAndDescription({ className = '' }: IPublicWorkspaceTitleAndDescriptionProps) {
    const workspace = useAppSelector((state) => state.workspace);

    const fullWorkspaceName = workspace?.title;

    return (
        <div className={`h-full w-full ${className}`}>
            <div className="w-full flex flex-col gap-2">
                <Tooltip title={trimTooltipTitle(fullWorkspaceName)}>
                    <h4 className="h5 w-fit">{fullWorkspaceName}</h4>
                </Tooltip>
                <MarkdownText className="lg:max-w-[700px] overflow-hidden " markDownClassName={'mt-0 text-sm text-black-600 font-normal'} text={toEndDottedStr(workspace.description, 277)} />
            </div>
        </div>
    );
}