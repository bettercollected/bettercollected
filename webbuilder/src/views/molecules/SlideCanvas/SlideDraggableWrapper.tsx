'use client';

import React, { useEffect, useLayoutEffect, useState } from 'react';

import { useDraggable } from '@app/lib/hooks/useDraggable';
import useElementSize from '@app/lib/hooks/useElementSize';

import './Canvas.css';

export interface ISlideDraggableWrapperProps {
    gridSize?: number;
    children: React.ReactNode | React.ReactNode[];
}

const SlideDraggableWrapper = ({
    gridSize = 5,
    children
}: ISlideDraggableWrapperProps) => {
    // Define a threshold distance for nearness
    const NEARNESS_THRESHOLD = 100;

    const [isDragging, setIsDragging] = useState(false);
    const [draggableWidth, setDraggableWidth] = useState(0);
    const [draggableHeight, setDraggableHeight] = useState(0);
    const [nearbyElements, setNearbyElements] = useState<Element[]>([]);
    const [elementColors, setElementColors] = useState<any>({});

    const [draggableRef, node, dx, dy] = useDraggable({
        gridSize
    });

    const navbarSize = useElementSize('#navbar');
    const slidesPreviewSize = useElementSize('#slides-preview');
    const canvasSize = useElementSize('#canvas');
    const slideElementPropertiesSize = useElementSize('#slide-element-properties');

    const handleDragStart = () => {
        setIsDragging(true);
    };

    const handleDragEnd = () => {
        setIsDragging(false);
    };

    const getRandomColor = (): string => {
        const letters: string = '0123456789ABCDEF';
        let color: string = '#';
        for (let i: number = 0; i < 6; i++) {
            color += letters[Math.floor(Math.random() * 16)];
        }
        return color + '4D';
    };

    // Set random color for an element if not already set
    const setRandomColorForElement = (index: number): void => {
        if (!elementColors[index]) {
            const color = getRandomColor();
            setElementColors((prevColors: { [key: number]: string }) => ({
                ...prevColors,
                [index]: color
            }));
        }
    };

    // Calculate dimensions of the dragging element
    useLayoutEffect(() => {
        if (node) {
            const { width, height } = node.getBoundingClientRect();
            setDraggableWidth(width);
            setDraggableHeight(height);
        }
    }, [node]);

    // Calculate nearby elements when the dragging element moves
    useEffect(() => {
        if (!node) return;

        const elements = Array.from(document.querySelectorAll('.draggable')).filter(
            (el) => el !== node
        );
        const nearby = elements.filter((element) => {
            const rect1 = node.getBoundingClientRect();
            const rect2 = element.getBoundingClientRect();

            const distanceTop = rect2.bottom - rect1.top;
            const distanceBottom = rect1.bottom - rect2.top;
            const distanceLeft = rect2.right - rect1.left;
            const distanceRight = rect1.right - rect2.left;

            return (
                distanceTop >= NEARNESS_THRESHOLD ||
                distanceBottom >= NEARNESS_THRESHOLD ||
                distanceLeft >= NEARNESS_THRESHOLD ||
                distanceRight >= NEARNESS_THRESHOLD
            );
        });

        // Don't remove this yet, this is needed for only nearby elements and above works for all elements
        // const nearby = elements.filter((element) => {
        //     const rect1 = node.getBoundingClientRect();
        //     const rect2 = element.getBoundingClientRect();

        //     const distanceX = Math.abs(
        //         rect1.left + rect1.width / 2 - (rect2.left + rect2.width / 2)
        //     );
        //     const distanceY = Math.abs(
        //         rect1.top + rect1.height / 2 - (rect2.top + rect2.height / 2)
        //     );

        //     return distanceX <= NEARNESS_THRESHOLD || distanceY <= NEARNESS_THRESHOLD;
        // });

        setNearbyElements(nearby);
    }, [dx, dy, node]);

    return (
        <>
            <div
                role="button"
                tabIndex={0}
                className="draggable"
                ref={draggableRef}
                style={{
                    transform: `translate3d(${dx}px, ${dy}px, 0)`
                }}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                onMouseDown={handleDragStart}
                onMouseUp={handleDragEnd}
                onTouchStart={handleDragStart}
                onTouchEnd={handleDragEnd}
            >
                {children}
            </div>
            {isDragging && (
                <>
                    {/* Top horizontal line */}
                    <div
                        style={{
                            position: 'absolute',
                            left: 0,
                            right: 0,
                            top: dy,
                            bottom: dy,
                            width: '100%',
                            height: '0.2px',
                            backgroundColor: 'rgba(7, 100, 235, 0.2)',
                            pointerEvents: 'none'
                        }}
                    ></div>

                    {/* Bottom horizontal line */}
                    <div
                        style={{
                            position: 'absolute',
                            left: 0,
                            right: 0,
                            top: dy + draggableHeight,
                            width: '100%',
                            height: '0.2px',
                            backgroundColor: 'rgba(7, 100, 235, 0.2)',
                            pointerEvents: 'none'
                        }}
                    ></div>

                    {/* Left vertical line */}
                    <div
                        style={{
                            position: 'absolute',
                            left: dx,
                            top: 0,
                            right: 0,
                            bottom: 0,
                            width: '0.2px',
                            height: '100vh',
                            backgroundColor: 'rgba(7, 100, 235, 0.2)',
                            pointerEvents: 'none'
                        }}
                    ></div>

                    {/* Right vertical line */}
                    <div
                        style={{
                            position: 'absolute',
                            left: dx + draggableWidth,
                            top: 0,
                            bottom: 0,
                            height: '100vh',
                            width: '0.2px',
                            backgroundColor: 'rgba(7, 100, 235, 0.2)',
                            pointerEvents: 'none'
                        }}
                    ></div>
                </>
            )}

            {/* Render nearby lines */}
            {isDragging &&
                nearbyElements.map((element, index) => {
                    setRandomColorForElement(index);
                    const color: string = elementColors[index];

                    return (
                        <React.Fragment key={index}>
                            {/* Top horizontal line */}
                            <div
                                style={{
                                    position: 'absolute',
                                    left: 0,
                                    right: 0,
                                    top:
                                        element.getBoundingClientRect().top -
                                        (navbarSize.height +
                                            slidesPreviewSize.marginTop),
                                    width: '100%',
                                    height: '0.2px',
                                    backgroundColor: color,
                                    pointerEvents: 'none'
                                }}
                            ></div>
                            {/* Bottom horizontal line */}
                            <div
                                style={{
                                    position: 'absolute',
                                    left: 0,
                                    right: 0,
                                    top:
                                        element.getBoundingClientRect().bottom -
                                        (navbarSize.height +
                                            slidesPreviewSize.marginTop),
                                    width: '100%',
                                    height: '0.2px',
                                    backgroundColor: color,
                                    pointerEvents: 'none'
                                }}
                            ></div>
                            {/* Left vertical line */}
                            <div
                                style={{
                                    position: 'absolute',
                                    left:
                                        element.getBoundingClientRect().left -
                                        slidesPreviewSize.width,
                                    top: 0,
                                    bottom: 0,
                                    width: '0.2px',
                                    height: '100vh',
                                    backgroundColor: color,
                                    pointerEvents: 'none'
                                }}
                            ></div>
                            {/* Right vertical line */}
                            <div
                                style={{
                                    position: 'absolute',
                                    left:
                                        element.getBoundingClientRect().right -
                                        slideElementPropertiesSize.width,
                                    top: 0,
                                    bottom: 0,
                                    height: '100vh',
                                    width: '0.2px',
                                    backgroundColor: color,
                                    // backgroundColor: 'rgba(255, 167, 22, 0.2)',
                                    pointerEvents: 'none'
                                }}
                            ></div>
                        </React.Fragment>
                    );
                })}
        </>
    );
};

export default SlideDraggableWrapper;
