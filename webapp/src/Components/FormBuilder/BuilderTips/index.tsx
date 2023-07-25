import React from 'react';

import FormBuilderBackspaceIcon from '@Components/Common/Icons/FormBuilderBackspaceIcon';
import FormBuilderDeleteIcon from '@Components/Common/Icons/FormBuilderDeleteIcon';
import FormBuilderDuplicateIcon from '@Components/Common/Icons/FormBuilderDuplicateIcon';
import FormBuilderEnterIcon from '@Components/Common/Icons/FormBuilderEnterIcon';
import FormBuilderEscapeIcon from '@Components/Common/Icons/FormBuilderEscapeIcon';
import FormBuilderSlashIcon from '@Components/Common/Icons/FormBuilderSlashIcon';
import FormBuilderSpotlightIcon from '@Components/Common/Icons/FormBuilderSpotlightIcon';
import KeyboardArrowDownIcon from '@Components/Common/Icons/KeyboardArrowDownIcon';
import KeyboardArrowUpIcon from '@Components/Common/Icons/KeyboardArrowUpIcon';

export default function BuilderTips() {
    const tips = [
        {
            Icon: <FormBuilderSlashIcon />,
            TextComponent: (
                <>
                    Hit <strong className="text-brand">/</strong> key to open the command in the field selection
                </>
            )
        },
        {
            Icon: <KeyboardArrowUpIcon />,
            TextComponent: (
                <>
                    Hit <strong className="text-brand">&uarr;</strong> arrow key to move up into different fields
                </>
            )
        },
        {
            Icon: <KeyboardArrowDownIcon />,
            TextComponent: (
                <>
                    Hit <strong className="text-brand">&darr;</strong> arrow key to move down into different fields
                </>
            )
        },
        {
            Icon: <FormBuilderEnterIcon />,
            TextComponent: (
                <>
                    Hit <strong className="text-brand">Enter</strong> key to add a new field
                </>
            )
        },
        {
            Icon: <FormBuilderEscapeIcon />,
            TextComponent: (
                <>
                    Hit <strong className="text-brand">Escape</strong> key to close spotlight, field selector, and field options
                </>
            )
        },
        {
            Icon: <FormBuilderSpotlightIcon />,
            TextComponent: (
                <>
                    Hit <strong className="text-brand">Ctrl/Cmd + K</strong> key to open the builder spotlight
                </>
            )
        },
        {
            Icon: <FormBuilderBackspaceIcon />,
            TextComponent: (
                <>
                    Hit <strong className="text-brand">Backspace</strong> key <strong>twice</strong> when the field is empty to focused the field
                </>
            )
        },
        {
            Icon: <FormBuilderDuplicateIcon />,
            TextComponent: (
                <>
                    Hit <strong className="text-brand">Ctrl/Cmd + D</strong> key to duplicate the focused field
                </>
            )
        },
        {
            Icon: <FormBuilderDeleteIcon />,
            TextComponent: (
                <>
                    Hit <strong className="text-brand">Ctrl/Cmd + Delete</strong> key to remove the focused field
                </>
            )
        }
    ];

    return (
        <div className="flex flex-col gap-4 mt-5 px-5 md:px-[89px]">
            {/* <p className="bg-black-300 rounded-[4px] body4 p-4 h-[42px] flex gap-1 items-center">
                Press
                <strong className="text-brand">
                    <i>Enter</i>
                </strong>
                key to add a new field or move downward into another field
            </p> */}
            <h1 className="uppercase font-bold tracking-wide text-brand">TIPS</h1>
            {tips.map((tip, index) => (
                <div key={index} className="flex items-center gap-4">
                    {tip.Icon}
                    <p className="flex gap-1 items-center body4">{tip.TextComponent}</p>
                </div>
            ))}
        </div>
    );
}
