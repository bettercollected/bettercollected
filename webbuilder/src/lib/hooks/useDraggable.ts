import React, { LegacyRef, useState } from 'react';

interface IDraggableProps {
    gridSize: number;
}

export const useDraggable = ({
    gridSize
}: IDraggableProps): [
    ref: (instance: HTMLDivElement | null) => void,
    node: HTMLDivElement | null | undefined,
    dx: number,
    dy: number
] => {
    const [node, setNode] = useState<HTMLDivElement>();
    const [{ dx, dy }, setOffset] = React.useState({
        dx: 20,
        dy: 20
    });

    // const [nearbyElements, setNearbyElements] = React.useState<
    //     HTMLElement[] | Element[]
    // >([]);

    const ref: LegacyRef<HTMLDivElement> | undefined = React.useCallback(
        (nodeEle: any) => {
            setNode(nodeEle);
        },
        []
    );

    const handleMouseMoveAxisSnap = (
        posA: { x: number; y: number },
        posB: { x: number; y: number },
        {
            parentElementRect,
            elementRect
        }: { parentElementRect: DOMRect; elementRect: DOMRect }
    ) => {
        let dx = posA.x - posB.x;
        let dy = posA.y - posB.y;

        // Find nearby elements
        // const elements = document.elementsFromPoint(posA.x, posA.y);
        // const nearby = elements.filter(
        //     (el) => el !== node && el.classList.contains('draggable')
        // );
        // setNearbyElements(nearby);

        // Snap to nearby elements if close enough
        // nearby.forEach((el) => {
        //     const rect = el.getBoundingClientRect();
        //     if (Math.abs(rect.left - posA.x) < gridSize / 2) {
        //         dx = rect.left - posB.x + rect.width / 2;
        //     }
        //     if (Math.abs(rect.top - posA.y) < gridSize / 2) {
        //         dy = rect.top - posB.y + rect.height / 2;
        //     }
        // });

        const snappedX = Math.round(dx / gridSize) * gridSize;
        const snappedY = Math.round(dy / gridSize) * gridSize;

        const clamp = (val: number, min: number, max: number): number =>
            Math.max(min, Math.min(max, val));

        let maxX = Infinity,
            maxY = Infinity;
        if (parentElementRect && elementRect) {
            maxX = parentElementRect.width - elementRect.width;
            maxY = parentElementRect.height - elementRect.height;
        }
        dx = clamp(snappedX, 0, maxX);
        dy = clamp(snappedY, 0, maxY);
        setOffset({ dx, dy });
        updateCursor();
    };

    const handleMouseDown = React.useCallback(
        (e: MouseEvent, parentElementRect: DOMRect, elementRect: DOMRect) => {
            const startPos = {
                x: e.clientX - dx,
                y: e.clientY - dy
            };

            const handleMouseMove = (e: MouseEvent) => {
                handleMouseMoveAxisSnap({ x: e.clientX, y: e.clientY }, startPos, {
                    parentElementRect,
                    elementRect
                });
            };

            const handleMouseUp = () => {
                document.removeEventListener('mousemove', handleMouseMove);
                document.removeEventListener('mouseup', handleMouseUp);
                resetCursor();
            };

            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [dx, dy]
    );

    const handleTouchStart = React.useCallback(
        (e: TouchEvent, parentElementRect: DOMRect, elementRect: DOMRect) => {
            const touch = e.touches[0];

            const startPos = {
                x: touch.clientX - dx,
                y: touch.clientY - dy
            };

            const handleTouchMove = (e: TouchEvent) => {
                const touch = e.touches[0];
                handleMouseMoveAxisSnap(
                    { x: touch.clientX, y: touch.clientY },
                    startPos,
                    { parentElementRect, elementRect }
                );
            };

            const handleTouchEnd = () => {
                document.removeEventListener('touchmove', handleTouchMove);
                document.removeEventListener('touchend', handleTouchEnd);
                resetCursor();
            };

            document.addEventListener('touchmove', handleTouchMove);
            document.addEventListener('touchend', handleTouchEnd);
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [dx, dy]
    );

    const updateCursor = () => {
        document.body.style.cursor = 'crosshair';
        document.body.style.userSelect = 'none';
    };

    const resetCursor = () => {
        document.body.style.removeProperty('cursor');
        document.body.style.removeProperty('user-select');
    };

    React.useEffect(() => {
        if (!node) return;

        const parentElement = node.parentElement;

        if (!parentElement) return;

        const parentElementRect = parentElement.getBoundingClientRect();
        const elementRect = node.getBoundingClientRect();

        node.addEventListener('mousedown', (e) =>
            handleMouseDown(e, parentElementRect, elementRect)
        );
        node.addEventListener('touchstart', (e) =>
            handleTouchStart(e, parentElementRect, elementRect)
        );
        return () => {
            node.removeEventListener('mousedown', (e) =>
                handleMouseDown(e, parentElementRect, elementRect)
            );
            node.removeEventListener('touchstart', (e) =>
                handleTouchStart(e, parentElementRect, elementRect)
            );
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [node, dx, dy]);

    return [ref, node, dx, dy];
};
