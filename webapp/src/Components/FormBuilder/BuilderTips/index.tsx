import React from 'react';

import _ from 'lodash';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { setBuilderState } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

import { tipsList } from './tipsList';

export default function BuilderTips() {
    const tips = tipsList().slice(0, 5);
    const { t } = useBuilderTranslation();
    const { openModal } = useModal();
    const builderState: IBuilderState = useAppSelector(selectBuilderState);
    const dispatch = useAppDispatch();

    const handleCloseIcon = () => {
        dispatch(
            setBuilderState({
                isFormDirty: true
            })
        );
    };

    return (
        <div className="flex flex-col gap-4 mt-5 ml-20 p-6 bg-black-200 rounded-2xl w-[540px]">
            <div className='flex justify-between mb-4'>
                <h1 className="uppercase font-bold tracking-wide text-black-900">{_.capitalize(t('TIPS.DEFAULT'))}:</h1>
                <Close onClick={handleCloseIcon} />
            </div>
            {tips.map((tip, index) => (
                <div key={index} className="flex flex-row gap-10">
                    <div className="flex items-center w-[86px] justify-end">{tip.Icon}</div>
                    <div className="body4 flex items-center">{tip.TextComponent}</div>
                </div>
            ))}
            <h1 className="h6-new !text-brand mt-8 cursor-pointer" onClick={() => openModal('FORM_BUILDER_TIPS_MODAL_VIEW')}>
                Show All
            </h1>
        </div>
    );
}
