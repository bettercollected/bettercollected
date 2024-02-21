'use client';

import React from 'react';

import { useScaling } from '@app/lib/hooks/useScaling';

import './Canvas.css';
import SlideDraggableWrapper from './SlideDraggableWrapper';

const SlideCanvas = () => {
    const scale = useScaling();

    console.log('scale', scale);

    return (
        <div id="canvas" className="canvas-grid container my-5" style={{ scale }}>
            <SlideDraggableWrapper>
                <p className="!m-0 !p-0">Drag first p tag</p>
            </SlideDraggableWrapper>
            <SlideDraggableWrapper>
                <p>Drag second p tag</p>
            </SlideDraggableWrapper>
            <SlideDraggableWrapper>
                <input type="text" />
            </SlideDraggableWrapper>
            <SlideDraggableWrapper>
                <h1>Drag h1</h1>
            </SlideDraggableWrapper>
        </div>
    );
};

export default SlideCanvas;
