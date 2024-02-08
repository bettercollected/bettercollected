'use client';

import React from 'react';

import './Canvas.css';
import SlideDraggableWrapper from './SlideDraggableWrapper';

const SlideCanvas = () => {
    return (
        <div className="canvas-grid container">
            <SlideDraggableWrapper>
                <p>Drag first p tag</p>
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
