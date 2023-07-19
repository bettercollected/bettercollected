import React, { FocusEvent, FormEvent, KeyboardEvent, useEffect, useRef } from 'react';

import ContentEditable, { ContentEditableEvent } from 'react-contenteditable';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

interface ICustomContentEditableProps {
    id: string;
    tagName: string;
    type: FormBuilderTagNames;
    placeholder: string;
    value: any;
    position: number;
    activeFieldIndex: number;
    className?: string;
    style?: Object;
    color?: string;
    translate?: 'yes' | 'no';
    hidden?: boolean;
    slot?: string;
    dir?: string;
    accessKey?: string;
    draggable?: boolean | 'false' | 'true';
    lang?: string;
    prefix?: string;
    role?: React.AriaRole;
    children?: React.ReactNode;
    inputMode?: 'search' | 'numeric' | 'none' | 'url' | 'text' | 'tel' | 'email' | 'decimal';
    nonce?: string;
    tabIndex?: number;
    defaultChecked?: boolean;
    defaultValue?: string | number | readonly string[];
    suppressContentEditableWarning?: boolean;
    suppressHydrationWarning?: boolean;
    contextMenu?: string;
    spellCheck?: boolean | 'false' | 'true';
    radioGroup?: string;
    about?: string;
    datatype?: string;
    inlist?: any;
    property?: string;
    resource?: string;
    typeof?: string;
    vocab?: string;
    autoCapitalize?: string;
    autoCorrect?: string;
    autoSave?: string;
    itemProp?: string;
    itemScope?: boolean;
    itemType?: string;
    itemID?: string;
    itemRef?: string;
    results?: number;
    security?: string;
    unselectable?: 'on' | 'off';
    is?: string;

    onCopyCallback?: React.ClipboardEventHandler<HTMLDivElement>;
    onCopyCaptureCallback?: React.ClipboardEventHandler<HTMLDivElement>;
    onCutCallback?: React.ClipboardEventHandler<HTMLDivElement>;
    onCutCaptureCallback?: React.ClipboardEventHandler<HTMLDivElement>;
    onPasteCallback?: React.ClipboardEventHandler<HTMLDivElement>;
    onPasteCaptureCallback?: React.ClipboardEventHandler<HTMLDivElement>;
    onCompositionEndCallback?: React.CompositionEventHandler<HTMLDivElement>;
    onCompositionEndCaptureCallback?: React.CompositionEventHandler<HTMLDivElement>;
    onCompositionStartCallback?: React.CompositionEventHandler<HTMLDivElement>;
    onCompositionStartCaptureCallback?: React.CompositionEventHandler<HTMLDivElement>;
    onCompositionUpdateCallback?: React.CompositionEventHandler<HTMLDivElement>;
    onCompositionUpdateCaptureCallback?: React.CompositionEventHandler<HTMLDivElement>;
    onFocusCallback?: React.FocusEventHandler<HTMLDivElement>;
    onFocusCaptureCallback?: React.FocusEventHandler<HTMLDivElement>;
    onBlurCaptureCallback?: React.FocusEventHandler<HTMLDivElement>;
    onChangeCaptureCallback?: React.FormEventHandler<HTMLDivElement>;
    onBeforeInputCallback?: React.FormEventHandler<HTMLDivElement>;
    onBeforeInputCaptureCallback?: React.FormEventHandler<HTMLDivElement>;
    onInputCaptureCallback?: React.FormEventHandler<HTMLDivElement>;
    onResetCallback?: React.FormEventHandler<HTMLDivElement>;
    onResetCaptureCallback?: React.FormEventHandler<HTMLDivElement>;
    onSubmitCallback?: React.FormEventHandler<HTMLDivElement>;
    onSubmitCaptureCallback?: React.FormEventHandler<HTMLDivElement>;
    onInvalidCallback?: React.FormEventHandler<HTMLDivElement>;
    onInvalidCaptureCallback?: React.FormEventHandler<HTMLDivElement>;
    onLoadCallback?: React.ReactEventHandler<HTMLDivElement>;
    onLoadCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onErrorCallback?: React.ReactEventHandler<HTMLDivElement>;
    onErrorCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onKeyDownCaptureCallback?: React.KeyboardEventHandler<HTMLDivElement>;
    onKeyPressCallback?: React.KeyboardEventHandler<HTMLDivElement>;
    onKeyPressCaptureCallback?: React.KeyboardEventHandler<HTMLDivElement>;
    onKeyUpCaptureCallback?: React.KeyboardEventHandler<HTMLDivElement>;
    onAbortCallback?: React.ReactEventHandler<HTMLDivElement>;
    onAbortCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onCanPlayCallback?: React.ReactEventHandler<HTMLDivElement>;
    onCanPlayCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onCanPlayThroughCallback?: React.ReactEventHandler<HTMLDivElement>;
    onCanPlayThroughCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onDurationChangeCallback?: React.ReactEventHandler<HTMLDivElement>;
    onDurationChangeCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onEmptiedCallback?: React.ReactEventHandler<HTMLDivElement>;
    onEmptiedCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onEncryptedCallback?: React.ReactEventHandler<HTMLDivElement>;
    onEncryptedCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onEndedCallback?: React.ReactEventHandler<HTMLDivElement>;
    onEndedCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onLoadedDataCallback?: React.ReactEventHandler<HTMLDivElement>;
    onLoadedDataCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onLoadedMetadataCallback?: React.ReactEventHandler<HTMLDivElement>;
    onLoadedMetadataCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onLoadStartCallback?: React.ReactEventHandler<HTMLDivElement>;
    onLoadStartCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onPauseCallback?: React.ReactEventHandler<HTMLDivElement>;
    onPauseCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onPlayCallback?: React.ReactEventHandler<HTMLDivElement>;
    onPlayCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onPlayingCallback?: React.ReactEventHandler<HTMLDivElement>;
    onPlayingCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onProgressCallback?: React.ReactEventHandler<HTMLDivElement>;
    onProgressCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onRateChangeCallback?: React.ReactEventHandler<HTMLDivElement>;
    onRateChangeCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onSeekedCallback?: React.ReactEventHandler<HTMLDivElement>;
    onSeekedCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onSeekingCallback?: React.ReactEventHandler<HTMLDivElement>;
    onSeekingCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onStalledCallback?: React.ReactEventHandler<HTMLDivElement>;
    onStalledCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onSuspendCallback?: React.ReactEventHandler<HTMLDivElement>;
    onSuspendCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onTimeUpdateCallback?: React.ReactEventHandler<HTMLDivElement>;
    onTimeUpdateCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onVolumeChangeCallback?: React.ReactEventHandler<HTMLDivElement>;
    onVolumeChangeCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onWaitingCallback?: React.ReactEventHandler<HTMLDivElement>;
    onWaitingCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onAuxClickCallback?: React.MouseEventHandler<HTMLDivElement>;
    onAuxClickCaptureCallback?: React.MouseEventHandler<HTMLDivElement>;
    onClickCallback?: React.MouseEventHandler<HTMLDivElement>;
    onClickCaptureCallback?: React.MouseEventHandler<HTMLDivElement>;
    onContextMenuCallback?: React.MouseEventHandler<HTMLDivElement>;
    onContextMenuCaptureCallback?: React.MouseEventHandler<HTMLDivElement>;
    onDoubleClickCallback?: React.MouseEventHandler<HTMLDivElement>;
    onDoubleClickCaptureCallback?: React.MouseEventHandler<HTMLDivElement>;
    onDragCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragCaptureCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragEndCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragEndCaptureCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragEnterCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragEnterCaptureCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragExitCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragExitCaptureCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragLeaveCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragLeaveCaptureCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragOverCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragOverCaptureCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragStartCallback?: React.DragEventHandler<HTMLDivElement>;
    onDragStartCaptureCallback?: React.DragEventHandler<HTMLDivElement>;
    onDropCallback?: React.DragEventHandler<HTMLDivElement>;
    onDropCaptureCallback?: React.DragEventHandler<HTMLDivElement>;
    onMouseDownCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseDownCaptureCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseEnterCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseLeaveCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseMoveCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseMoveCaptureCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseOutCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseOutCaptureCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseOverCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseOverCaptureCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseUpCallback?: React.MouseEventHandler<HTMLDivElement>;
    onMouseUpCaptureCallback?: React.MouseEventHandler<HTMLDivElement>;
    onSelectCallback?: React.ReactEventHandler<HTMLDivElement>;
    onSelectCaptureCallback?: React.ReactEventHandler<HTMLDivElement>;
    onTouchCancelCallback?: React.TouchEventHandler<HTMLDivElement>;
    onTouchCancelCaptureCallback?: React.TouchEventHandler<HTMLDivElement>;
    onTouchEndCallback?: React.TouchEventHandler<HTMLDivElement>;
    onTouchEndCaptureCallback?: React.TouchEventHandler<HTMLDivElement>;
    onTouchMoveCallback?: React.TouchEventHandler<HTMLDivElement>;
    onTouchMoveCaptureCallback?: React.TouchEventHandler<HTMLDivElement>;
    onTouchStartCallback?: React.TouchEventHandler<HTMLDivElement>;
    onTouchStartCaptureCallback?: React.TouchEventHandler<HTMLDivElement>;
    onPointerDownCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerDownCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerMoveCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerMoveCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerUpCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerUpCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerCancelCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerCancelCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerEnterCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerEnterCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerLeaveCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerLeaveCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerOverCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerOverCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerOutCallback?: React.PointerEventHandler<HTMLDivElement>;
    onPointerOutCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onGotPointerCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onGotPointerCaptureCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onLostPointerCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onLostPointerCaptureCaptureCallback?: React.PointerEventHandler<HTMLDivElement>;
    onScrollCallback?: React.UIEventHandler<HTMLDivElement>;
    onScrollCaptureCallback?: React.UIEventHandler<HTMLDivElement>;
    onWheelCallback?: React.WheelEventHandler<HTMLDivElement>;
    onWheelCaptureCallback?: React.WheelEventHandler<HTMLDivElement>;
    onAnimationStartCallback?: React.AnimationEventHandler<HTMLDivElement>;
    onAnimationStartCaptureCallback?: React.AnimationEventHandler<HTMLDivElement>;
    onAnimationEndCallback?: React.AnimationEventHandler<HTMLDivElement>;
    onAnimationEndCaptureCallback?: React.AnimationEventHandler<HTMLDivElement>;
    onAnimationIterationCallback?: React.AnimationEventHandler<HTMLDivElement>;
    onAnimationIterationCaptureCallback?: React.AnimationEventHandler<HTMLDivElement>;
    onTransitionEndCallback?: React.TransitionEventHandler<HTMLDivElement>;
    onTransitionEndCaptureCallback?: React.TransitionEventHandler<HTMLDivElement>;

    onChangeCallback: (event: FormEvent<HTMLElement>) => void;
    onBlurCallback?: React.FocusEventHandler<HTMLDivElement>;
    onKeyUpCallback?: React.KeyboardEventHandler<HTMLDivElement>;
    onKeyDownCallback?: React.KeyboardEventHandler<HTMLDivElement>;
}

export default function CustomContentEditable({ id, tagName, type, placeholder, value, position, activeFieldIndex, className = '', onChangeCallback, onKeyUpCallback, onKeyDownCallback, onFocusCallback, onBlurCallback }: ICustomContentEditableProps) {
    const contentEditableRef = useRef<HTMLElement>(null);

    const onChangeHandler = (event: ContentEditableEvent) => {
        onChangeCallback(event);
    };

    const onFocusHandler = (event: FocusEvent<HTMLDivElement>) => {
        if (onFocusCallback) onFocusCallback(event);
    };

    const onBlurHandler = (event: FocusEvent<HTMLDivElement>) => {
        if (onBlurCallback) onBlurCallback(event);
    };

    const onKeyUpHandler = (event: KeyboardEvent<HTMLDivElement>) => {
        if (onKeyUpCallback) onKeyUpCallback(event);
    };

    const onKeyDownHandler = (event: KeyboardEvent<HTMLDivElement>) => {
        if (onKeyDownCallback) onKeyDownCallback(event);
    };

    useEffect(() => {
        // Focus on the first contentEditable element (title) when the page loads
        if (position !== activeFieldIndex) return;

        contentEditableRef.current?.focus();

        // Set the cursor position to 0 when the page loads
        const range = document.createRange();

        if (contentEditableRef?.current) {
            range.selectNodeContents(contentEditableRef.current);
            range.collapse(true);
        }
        const selection = window.getSelection();
        if (selection) {
            selection.removeAllRanges();
            selection.addRange(range);
        }
    }, [position, activeFieldIndex]);

    return (
        <ContentEditable
            id={id}
            contentEditable
            spellCheck={false}
            innerRef={contentEditableRef}
            html={value}
            tagName={tagName}
            data-placeholder={placeholder}
            data-position={position}
            data-type={type}
            className={`m-0 p-0 w-full cursor-text focus-visible:border-0 focus-visible:outline-none ${className}`}
            onChange={onChangeHandler}
            onFocus={onFocusHandler}
            onBlur={onBlurHandler}
            onKeyUp={onKeyUpHandler}
            onKeyDown={onKeyDownHandler}
        />
    );
}
