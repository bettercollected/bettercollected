import React from 'react';

import _ from 'lodash';

import FormBuilderBackspaceIcon from '@Components/Common/Icons/FormBuilderBackspaceIcon';
import FormBuilderDeleteIcon from '@Components/Common/Icons/FormBuilderDeleteIcon';
import FormBuilderDuplicateIcon from '@Components/Common/Icons/FormBuilderDuplicateIcon';
import FormBuilderEnterIcon from '@Components/Common/Icons/FormBuilderEnterIcon';
import FormBuilderEscapeIcon from '@Components/Common/Icons/FormBuilderEscapeIcon';
import FormBuilderSlashIcon from '@Components/Common/Icons/FormBuilderSlashIcon';
import FormBuilderSpotlightIcon from '@Components/Common/Icons/FormBuilderSpotlightIcon';
import KeyboardArrowDownIcon from '@Components/Common/Icons/KeyboardArrowDownIcon';
import KeyboardArrowUpIcon from '@Components/Common/Icons/KeyboardArrowUpIcon';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';

export default function BuilderTips() {
    const isMac = typeof window !== 'undefined' ? navigator.userAgent.toUpperCase().indexOf('MAC') >= 0 : false;
    const commandKeyString = isMac ? 'Command' : 'Ctrl';

    const { t } = useBuilderTranslation();

    const tips = [
        {
            Icon: <FormBuilderSlashIcon />,
            TextComponent: (
                <>
                    {t('TIPS.HIT')} <strong className="text-brand">/</strong> {t('TIPS.ACTIONS.COMMAND')}
                </>
            )
        },
        {
            Icon: <FormBuilderEnterIcon />,
            TextComponent: (
                <div className="flex flex-col gap-2">
                    <div className="flex justify-start items-center gap-1">
                        {t('TIPS.HIT')} <strong className="text-brand">Enter</strong> {t('TIPS.ACTIONS.ENTER')}
                    </div>
                    <div className="flex justify-start items-center gap-1">
                        {t('TIPS.HIT')} <strong className="text-brand">{commandKeyString} + I</strong> {t('TIPS.ACTIONS.CTRL_I')}
                    </div>
                </div>
            )
        },
        {
            Icon: <FormBuilderEscapeIcon />,
            TextComponent: (
                <>
                    {t('TIPS.HIT')} <strong className="text-brand">Escape</strong> {t('TIPS.ACTIONS.ESC')}
                </>
            )
        },
        {
            Icon: <FormBuilderBackspaceIcon />,
            TextComponent: (
                <>
                    {t('TIPS.HIT')} <strong className="text-brand">Backspace</strong> {t('TIPS.ACTIONS.BACKSPACE')}
                </>
            )
        },
        {
            Icon: <KeyboardArrowUpIcon />,
            TextComponent: (
                <div className="flex flex-col gap-2">
                    <div className="flex justify-start items-center gap-1">
                        {t('TIPS.HIT')} <strong className="text-brand">&uarr;</strong> {t('TIPS.ACTIONS.UP')}
                    </div>
                    <div className="flex justify-start items-center gap-1">
                        {t('TIPS.HIT')} <strong className="text-brand">{commandKeyString} + &uarr;</strong> {t('TIPS.ACTIONS.CTRL_UP')}
                    </div>
                </div>
            )
        },
        {
            Icon: <KeyboardArrowDownIcon />,
            TextComponent: (
                <div className="flex flex-col gap-2">
                    <div className="flex justify-start items-center gap-1">
                        {t('TIPS.HIT')} <strong className="text-brand">&darr;</strong> {t('TIPS.ACTIONS.DOWN')}
                    </div>
                    <div className="flex justify-start items-center gap-1">
                        {t('TIPS.HIT')} <strong className="text-brand">{commandKeyString} + &darr;</strong> {t('TIPS.ACTIONS.CTRL_DOWN')}
                    </div>
                </div>
            )
        },

        {
            Icon: <FormBuilderSpotlightIcon />,
            TextComponent: (
                <>
                    {t('TIPS.HIT')} <strong className="text-brand">{commandKeyString} + K</strong> {t('TIPS.ACTIONS.CTRL_K')}
                </>
            )
        },
        {
            Icon: <FormBuilderDuplicateIcon />,
            TextComponent: (
                <>
                    {t('TIPS.HIT')} <strong className="text-brand">{commandKeyString} + S</strong> {t('TIPS.ACTIONS.CTRL_S')}
                </>
            )
        },
        {
            Icon: <FormBuilderDuplicateIcon />,
            TextComponent: (
                <>
                    {t('TIPS.HIT')} <strong className="text-brand">{commandKeyString} + P</strong> {t('TIPS.ACTIONS.CTRL_P')}
                </>
            )
        },
        {
            Icon: <FormBuilderDuplicateIcon />,
            TextComponent: (
                <>
                    {t('TIPS.HIT')} <strong className="text-brand">{commandKeyString} + D</strong> {t('TIPS.ACTIONS.CTRL_D')}
                </>
            )
        },
        {
            Icon: <FormBuilderDeleteIcon />,
            TextComponent: (
                <>
                    {t('TIPS.HIT')} <strong className="text-brand">{commandKeyString} + Delete</strong> {t('TIPS.ACTIONS.CTRL_DELETE')}
                </>
            )
        }
    ];

    return (
        <div className="flex flex-col gap-4 mt-5 px-5 md:px-[89px]">
            {/* <p className="bg-black-300 rounded-[4px] body4 p-4 h-[42px] flex gap-1 items-center">
                <strong className="text-brand uppercase mr-2">Note:</strong>
                If you are on macOS, use <strong>Command (Cmd)</strong> key instead of <strong>Control (Ctrl)</strong> key.
            </p> */}
            <h1 className="uppercase font-bold tracking-wide text-brand">{_.capitalize(t('TIPS.DEFAULT'))}</h1>
            {tips.map((tip, index) => (
                <div key={index} className="flex items-start gap-4">
                    {tip.Icon}
                    <div className="flex gap-1 items-center body4">{tip.TextComponent}</div>
                </div>
            ))}
        </div>
    );
}
