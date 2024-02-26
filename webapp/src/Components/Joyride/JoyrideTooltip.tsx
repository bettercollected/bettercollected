import React from 'react';



import Button from '@mui/material/Button';
import { TooltipRenderProps } from 'react-joyride';


// Currently not used, used the default one by modifying it's styles
export default function JoyrideTooltip({ continuous, index, step, backProps, closeProps, primaryProps, tooltipProps, isLastStep, size }: TooltipRenderProps) {
    return (
        <div {...tooltipProps} className="bg-white p-6 rounded w-80 flex flex-col gap-4">
            {step.title && <div className="w-full h-full">{step.title}</div>}
            <div className="w-full h-full">{step.content}</div>
            <div className="w-full h-full flex justify-end gap-4">
                {index > 0 && (
                    <Button className="capitalize" variant="text" color="inherit" {...backProps}>
                        Back
                    </Button>
                )}
                {(!continuous || index === 0) && (
                    <Button className="capitalize" variant="text" color="error" {...closeProps}>
                        Close
                    </Button>
                )}
                {continuous && (
                    <Button className="capitalize" variant="text" color="primary" {...primaryProps}>
                        {isLastStep ? 'Last Step' : `Next (${index + 1} / ${size})`}
                    </Button>
                )}
            </div>
        </div>
    );
}