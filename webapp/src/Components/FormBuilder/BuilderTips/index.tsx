import React from 'react';

import FormBuilderEnterIcon from '@Components/Common/Icons/FormBuilderEnterIcon';
import FormBuilderSlashIcon from '@Components/Common/Icons/FormBuilderSlashIcon';
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
            Icon: <FormBuilderEnterIcon />,
            TextComponent: (
                <>
                    Hit <strong className="text-brand">Enter</strong> key to add a new field
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
        }
    ];

    return (
        <div className="flex flex-col gap-4 px-5 md:px-[89px]">
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
