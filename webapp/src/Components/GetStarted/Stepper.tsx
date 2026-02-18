import React from 'react';

import { useTranslation } from 'next-i18next';

import Chevron from '@Components/Common/Icons/Common/Chevron';
import MobileStepper from '@mui/material/MobileStepper';
import { withStyles } from '@mui/styles';
import { Button } from '@app/shadcn/components/ui/button';

import { buttonConstant } from '@app/constants/locales/button';


const CustomMobileStepper: any = withStyles({
    progress: {
        backgroundColor: '#CED4DA',
        color: '#343A40',
        borderRadius: '12px',
        height: '12px'
    }
})(MobileStepper);

interface IGetStartedStepperProps {
    activeStep: number;
    steps: number;
    handleBack: () => void;
}

export default function GetStartedStepper({ steps, activeStep, handleBack }: IGetStartedStepperProps) {
    const { t } = useTranslation();
    return (
        <CustomMobileStepper
            variant="progress"
            steps={steps}
            position="static"
            activeStep={activeStep}
            sx={{ width: '100%', background: 'transparent', flexGrow: 1 }}
            backButton={
                <Button variant="ghost" onClick={handleBack} className="mr-[40px] flex justify-center items-center body4 capitalize gap-3 !text-black-700 hover:bg-brand-100 hover:underline">
                    <div className="!rotate-90 transition-all duration-300">
                        <Chevron width={24} height={24} />
                    </div>
                    {t(buttonConstant.back)}
                </Button>
            }
        />
    );
}