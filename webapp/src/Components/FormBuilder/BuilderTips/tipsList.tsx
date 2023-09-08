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

export const tipsList = () => {
    const isMac = typeof window !== 'undefined' ? navigator.userAgent.toUpperCase().indexOf('MAC') >= 0 : false;
    const commandKeyString = isMac ? 'Command' : 'Ctrl';

    const { t } = useBuilderTranslation();

    const tips = [
        {
            Icon: <div className="h6-new !text-black-800">/</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.COMMAND')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">&uarr;</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.UP')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">&darr;</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.DOWN')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">Enter</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.ENTER')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">Backspace</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.BACKSPACE')}</div>
        },

        {
            Icon: <div className="h6-new !text-black-800">Ctrl + K</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_K')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">Ctrl + P</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_P')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">Ctrl + D</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_D')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">Ctrl + I</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_I')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">Ctrl + &darr;</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_DOWN')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">Ctrl + &uarr;</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_UP')}</div>
        },
        {
            Icon: <div className="h6-new !text-black-800">Ctrl + Delete</div>,
            TextComponent: <div className="!text-black-800">{t('TIPS.ACTIONS.CTRL_DELETE')}</div>
        }
    ];

    return tips;
};
