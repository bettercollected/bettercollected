'use client';

import React, { useEffect, useRef, useState } from 'react';

import { useDraggable } from '@app/lib/hooks/useDraggable';

import './Canvas.css';

interface ISlideDraggableWrapperProps {
    gridSize?: number;
    children: React.ReactNode | React.ReactNode[];
}

const SlideDraggableWrapper = ({
    gridSize = 5,
    children
}: ISlideDraggableWrapperProps) => {
    const [isDragging, setIsDragging] = useState(false);
    const [draggableWidth, setDraggableWidth] = useState(0);
    const [draggableHeight, setDraggableHeight] = useState(0);

    const [draggableRef, node, dx, dy] = useDraggable({
        gridSize
    });

    const ref = useRef<HTMLDivElement | null>(null);

    const handleDragStart = () => {
        setIsDragging(true);
    };

    const handleDragEnd = () => {
        setIsDragging(false);
    };

    useEffect(() => {
        if (ref.current === null && !!node) {
            ref.current = node;
        }
        const draggableElement = ref.current;

        if (!draggableElement) return;

        let draggableWidth = 0;
        let draggableHeight = 0;

        const { width, height } = draggableElement.getBoundingClientRect();
        draggableWidth = width;
        draggableHeight = height;

        setDraggableHeight(draggableHeight);
        setDraggableWidth(draggableWidth);
    }, [node]);

    return (
        <>
            <div
                role="button"
                tabIndex={0}
                className={`draggable ${isDragging ? 'dragging' : ''}`}
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
                            height: '100vh',
                            width: '0.2px',
                            backgroundColor: 'rgba(7, 100, 235, 0.2)',
                            pointerEvents: 'none'
                        }}
                    ></div>
                </>
            )}
        </>
    );
};

export default SlideDraggableWrapper;
