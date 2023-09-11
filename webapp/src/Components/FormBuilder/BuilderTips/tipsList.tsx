import React from 'react';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';

interface ITipElement {
    Icon: React.ReactElement;
    TextComponent: React.ReactElement;
}

interface ITipListProps {
    className: string;
    listNumber?: number;
}

export const TipList = ({ className, listNumber }: ITipListProps) => {
    const isMac = typeof window !== 'undefined' ? navigator.userAgent.toUpperCase().indexOf('MAC') >= 0 : false;
    const commandKeyString = isMac ? 'Command' : 'Ctrl';

    const { t } = useBuilderTranslation();

    const tipsItems = [
        {
            Icon: <div className="h6-new !text-black-800">/</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.COMMAND')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">Enter</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.ENTER')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">{commandKeyString} + I</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_I')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">{commandKeyString} + K</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_K')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">Backspace</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.BACKSPACE')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">{commandKeyString} + Delete</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_DELETE')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">{commandKeyString} + P</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_P')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">{commandKeyString} + D</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_D')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">{commandKeyString} + &uarr;</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_UP')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">{commandKeyString} + &darr;</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_DOWN')}</div>
        },

        {
            Icon: <div className="h6-new !text-black-800">&uarr;</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.UP')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">&darr;</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.DOWN')}</div>
        }
    ];
    const tips = tipsItems.slice(0, listNumber);
    return (
        <>
            {tips.map((tip: ITipElement, index) => {
                return (
                    <div key={index} className={className}>
                        <div className="flex items-center w-24 justify-end">{tip.Icon}</div>
                        <div className="body4 flex items-center">{tip.TextComponent}</div>
                    </div>
                );
            })}
        </>
    );
};
