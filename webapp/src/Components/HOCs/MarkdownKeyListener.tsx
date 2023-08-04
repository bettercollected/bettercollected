import React, { useEffect } from 'react';

import { KeyType } from '@app/models/enums/formBuilder';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { useAppSelector } from '@app/store/hooks';

export default function MarkdownKeyListener({ children }: React.PropsWithChildren) {
    const builderState = useAppSelector(selectBuilderState);
    const { activeFieldId, activeFieldIndex } = builderState;

    const onKeyDownCallback = (event: KeyboardEvent) => {
        if (builderState.fields[activeFieldId]?.position !== activeFieldIndex) return;
        if (event.key === KeyType.ArrowUp || event.key === KeyType.ArrowDown) {
            event.stopPropagation();
            event.stopImmediatePropagation();
        }
    };
    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            onKeyDownCallback(event);
        };

        document.addEventListener('keydown', handleKeyDown);

        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    });

    return <div>{children}</div>;
}
