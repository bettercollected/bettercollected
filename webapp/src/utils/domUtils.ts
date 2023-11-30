export function focusElementByIdWithDelay(id: string) {
    setTimeout(() => document.getElementById(id)?.focus(), 1);
}

export function focusElementById(id: string) {
    document.getElementById(id)?.focus();
}

export const getTextWidth = (text?: string) => {
    const fontSize = 14;
    const fontFamily = 'Inter';

    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    context!.font = `${fontSize}px ${fontFamily}`;
    const width = context?.measureText(text || '').width;
    // Remove the temporary canvas element
    canvas.parentNode?.removeChild(canvas);
    return width;
};
