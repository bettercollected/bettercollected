import React, { ComponentType, useEffect, useState } from 'react';

import SlideDraggableWrapper, {
    ISlideDraggableWrapperProps
} from './SlideDraggableWrapper';

interface CanvasScalerProps {
    canvasElement: HTMLElement | null;
}

// Higher Order Component (HOC) to scale down children elements based on canvas size
const CanvasScaler = <P extends ISlideDraggableWrapperProps>(
    WrappedComponent: ComponentType<P>
) => {
    const WrappedComponentWithCanvasScale: React.FC<CanvasScalerProps & P> = (
        props
    ) => {
        const { canvasElement, ...rest } = props;
        const [scale, setScale] = useState(1);

        useEffect(() => {
            const calculateScale = () => {
                if (canvasElement) {
                    const canvasComputedStyle = window.getComputedStyle(canvasElement);
                    const canvasWidth = parseFloat(canvasComputedStyle.width);
                    const canvasHeight = parseFloat(canvasComputedStyle.height);

                    const canvasAspectRatio = 16 / 9;
                    const currentAspectRatio = canvasWidth / canvasHeight;
                    if (currentAspectRatio < canvasAspectRatio) {
                        setScale(canvasWidth / (16 * 16)); // Assuming 16 is the minimum canvas width
                    } else {
                        setScale(canvasHeight / (9 * 16)); // Assuming 9 is the minimum canvas height
                    }
                }
            };

            calculateScale();

            window.addEventListener('resize', calculateScale);

            return () => {
                window.removeEventListener('resize', calculateScale);
            };
        }, [canvasElement]);

        return (
            <div style={{ transform: `scale(${scale})`, transformOrigin: 'top left' }}>
                <WrappedComponent {...(rest as unknown as P)} />
            </div>
        );
    };

    return WrappedComponentWithCanvasScale;
};

const SlideDraggableWithScaling = CanvasScaler(SlideDraggableWrapper);

export default SlideDraggableWithScaling;
