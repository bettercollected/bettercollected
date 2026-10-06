import React from 'react';

import { useTranslation } from 'react-i18next';

import { Close } from '@app/components/icons/close';
import { buttonConstant } from '@app/constants/locales/button';
import { cn } from '@app/shadcn/util/lib';

interface ModalCloseButtonProps {
    onClick: () => void;
    /** Positioning and sizing of the button; the icon fills it. */
    className?: string;
    iconClassName?: string;
    /** Accessible name; defaults to the translated "Close". */
    label?: string;
}

/**
 * The X that closes a modal: a real, labelled button (keyboard reachable,
 * announced as "Close") instead of a bare clickable icon.
 */
export default function ModalCloseButton({ onClick, className, iconClassName, label }: ModalCloseButtonProps) {
    const { t } = useTranslation();
    return (
        <button
            type="button"
            onClick={onClick}
            aria-label={label ?? t(buttonConstant.close)}
            className={cn('flex items-center justify-center rounded-md text-black-700 hover:bg-black-200 hover:text-black-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500', className)}
        >
            <Close aria-hidden="true" className={cn('h-4 w-4', iconClassName)} />
        </button>
    );
}
