import React from 'react';

import { tipsList } from '@Components/FormBuilder/BuilderTips/tipsList';
import { Divider } from '@mui/material';

import { Close } from '@app/components/icons/close';

import { useModal } from '../context';

interface ITipElement {
    Icon: React.ReactElement;
    TextComponent: React.ReactElement;
}

interface ITipElements {
    tips: ITipElement[];
}

const FormBuilderTipsModalView = () => {
    const { closeModal } = useModal();
    const tips = tipsList();
    return (
        <div className="h-[465px] md:w-[792px] bg-white rounded-2xl overflow-hidden">
            <div className="px-6 flex justify-between py-4">
                <h1>Tips</h1>
                <Close onClick={() => closeModal()} />
            </div>
            <Divider />
            <div className="p-4 md:p-6 flex flex-col">
                <h1 className="sh1">Shortcut:</h1>
                <div className="flex flex-col flex-wrap gap-1 w-fit md:gap-6 p-2 md:p-4 md:pb-10 h-[350px]">
                    <TipElements tips={tips} />
                </div>
            </div>
        </div>
    );
};

const TipElements = ({ tips }: ITipElements) => {
    return (
        <>
            {tips.map((tip:ITipElement, index) => {
                return (
                    <div key={index} className="flex flex-row gap-4 md:gap-10">
                        <div className="flex items-center w-24 justify-end">{tip.Icon}</div>
                        <div className="body4 flex items-center">{tip.TextComponent}</div>
                    </div>
                );
            })}
        </>
    );
};

export default FormBuilderTipsModalView;
