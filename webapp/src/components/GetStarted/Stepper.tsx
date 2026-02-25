// @ts-nocheck
import React from 'react';

import { useTranslation } from 'next-i18next';

import Chevron from '@Components/Common/Icons/Common/Chevron';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';

import { buttonConstant } from '@app/constants/locales/button';

interface IGetStartedStepperProps {
    activeStep: number;
    steps: number;
    handleBack: () => void;
}

export default function GetStartedStepper({ steps, activeStep, handleBack }: IGetStartedStepperProps) {
    const { t } = useTranslation();

    // Calculate progress percentage
    // Logic: (activeStep + 1 / steps) * 100
    const progress = Math.min(100, Math.ceil(((activeStep + 1) / steps) * 100));

    return (
        <div className="flex w-full items-center justify-between gap-4 bg-transparent flex-grow">
            <Button variant="ghost" onClick={handleBack} className="mr-[40px] flex justify-center items-center gap-3 text-sm capitalize text-black-700 hover:bg-brand-100 hover:underline px-4">
                <div className="rotate-90 transition-all duration-300">
                    <Chevron width={24} height={24} className="fill-current" />
                </div>
                {t(buttonConstant.back)}
            </Button>

            <div className="h-[12px] flex-grow bg-[#CED4DA] rounded-[12px] overflow-hidden">
                <div
                    className="h-full bg-[#343A40] transition-all duration-300 ease-in-out rounded-[12px]"
                    style={{ width: `${progress}%` }}
                />
            </div>
        </div>
    );
}
