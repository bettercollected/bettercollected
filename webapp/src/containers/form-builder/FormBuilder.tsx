import React, { FormEvent, useCallback, useEffect, useRef, useState } from 'react';

import { useRouter } from 'next/router';

import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock';
import BuilderTips from '@Components/FormBuilder/BuilderTips';
import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';
import BuilderDragDropContext from '@Components/FormBuilder/DragDropContext';
import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import { DragStart, DragUpdate, DropResult, ResponderProvided } from 'react-beautiful-dnd';
import ContentEditable from 'react-contenteditable';
import { batch } from 'react-redux';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import eventBus from '@app/lib/event-bus';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import useUserTypingDetection from '@app/lib/hooks/use-user-typing-detection';
import useUndoRedo from '@app/lib/use-undo-redo';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import EventBusEventType from '@app/models/enums/eventBusEnum';
import { resetBuilderMenuState, setActiveField, setAddNewField, setBuilderState, setFields } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IBuilderTitleAndDescriptionObj, IFormFieldState } from '@app/store/form-builder/types';
import { builderTitleAndDescriptionList } from '@app/store/form-builder/utils';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateFormMutation, usePatchFormMutation } from '@app/store/workspaces/api';
import { reorder } from '@app/utils/arrayUtils';
import { createNewField } from '@app/utils/formBuilderBlockUtils';
import { throttle } from '@app/utils/throttleUtils';

import useFormBuilderState from './context';

export default function FormBuilder({ workspace, _nextI18Next, isEditMode = false }: { isEditMode?: boolean; workspace: WorkspaceDto; _nextI18Next: any }) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const { t } = useBuilderTranslation();
    const { handleUserTypingEnd } = useUserTypingDetection();
    const { isUndoRedoInProgress } = useUndoRedo();
    const builderDragDropRef = useRef<HTMLDivElement | null>(null);

    const router = useRouter();

    const builderState: IBuilderState = useAppSelector(selectBuilderState);
    const onBlurCallbackRef = useRef<any>(null);

    const { backspaceCount, setBackspaceCount } = useFormBuilderState();

    const [postCreateForm] = useCreateFormMutation();
    const [patchForm] = usePatchFormMutation();

    const fullScreenModal = useFullScreenModal();
    const modal = useModal();
    //
    const locale = _nextI18Next.initialLocale === 'en' ? '' : `${_nextI18Next.initialLocale}/`;

    const onInsert = () => {
        asyncDispatch(resetBuilderMenuState()).then(() => {
            modal.openModal('FORM_BUILDER_ADD_FIELD_VIEW');
        });
    };

    const onAddNewPage = () => {};

    const onAddFormLogo = () => {};

    const onAddFormCover = () => {};

    const onPreview = () => {
        asyncDispatch(resetBuilderMenuState()).then(() => {
            fullScreenModal.openModal('FORM_BUILDER_PREVIEW', { publish: onFormPublish });
        });
    };

    const onBlurCallback = useCallback(
        (event: FocusEvent) => {
            event.preventDefault();
            setBackspaceCount(0);
            dispatch(
                setBuilderState({
                    menus: {
                        ...builderState.menus,
                        commands: { isOpen: false, atFieldUuid: '', position: 'down' }
                    }
                })
            );
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [builderState, backspaceCount]
    );

    const onFormPublishRedirect = (response: any) => {
        const redirectUrl = !isEditMode ? `/${workspace?.workspaceName}/dashboard` : `/${locale}${workspace?.workspaceName}/dashboard/forms/${builderState.id}`;
        const createUpdateText = !isEditMode ? 'creat' : 'updat';

        if (response?.data) {
            toast(`Form ${createUpdateText}ed!!`, { type: 'success' });
            asyncDispatch(setBuilderState({ isFormDirty: false })).then(async () => {
                await router.push(redirectUrl);
            });
        } else {
            toast(`Error ${createUpdateText}ing form`, { type: 'error' });
        }
    };

    const onFormSave = async (isPublishClicked = false) => {
        const apiCall = !isEditMode ? postCreateForm : patchForm;

        const publishRequest: any = {};
        publishRequest.title = builderState.title;
        publishRequest.description = builderState.description;
        let fields: any = Object.values(builderState.fields || {});
        fields = fields.map((field: IFormFieldState) => {
            if (field.properties?.choices) {
                return { ...field, properties: { ...field.properties, choices: Object.values(field.properties?.choices) } };
            }
            return field;
        });
        console.log({ fields });
        publishRequest.fields = fields;
        publishRequest.settings = builderState.settings;
        publishRequest.buttonText = builderState.buttonText;
        const apiObj: any = { workspaceId: workspace.id, body: publishRequest };
        if (isEditMode) apiObj['formId'] = builderState?.id;

        const response: any = await apiCall(apiObj);
        if (response?.data && !isPublishClicked) {
            toast('Form saved!', { type: 'success' });
            if (!isEditMode) router.push(`/${locale}${workspace?.workspaceName}/dashboard/forms/${response?.data?.formId}/edit`);
            dispatch(setBuilderState({ isFormDirty: false }));
        }
        return response;
    };

    const onFormPublish = async () => {
        const response = await onFormSave(true);
        onFormPublishRedirect(response);
    };

    const openTagSelector = (event: any) => {
        const viewportHeight = window.innerHeight;
        const boundingRect = event.target.getBoundingClientRect();
        const bottomPosition = boundingRect.bottom ?? 0;

        // 300 is the height of the FormBuilderTagSelector
        dispatch(
            setBuilderState({
                isFormDirty: true,
                menus: {
                    ...builderState.menus,
                    commands: {
                        isOpen: true,
                        atFieldUuid: Object.keys(builderState.fields).at(builderState.activeFieldIndex) ?? '',
                        position: bottomPosition + 300 > viewportHeight ? 'up' : 'down'
                    }
                }
            })
        );
    };

    const getAddFieldPrompt = (
        <>
            <div className="h-20 group-hover:h-0"></div>
            <div className="invisible py-2 px-4 bg-gray-50 font-medium text-gray-400 rounded-md text-sm group-hover:visible">Click to add new field</div>
        </>
    );
    useEffect(() => {
        onBlurCallbackRef.current = throttle(onBlurCallback, 100);
        document.addEventListener('blur', onBlurCallback);

        // Listens events from the HOCs
        eventBus.on(EventBusEventType.FormBuilder.Save, onFormSave);
        eventBus.on(EventBusEventType.FormBuilder.Publish, onFormPublish);
        eventBus.on(EventBusEventType.FormBuilder.OpenTagSelector, openTagSelector);

        return () => {
            eventBus.removeListener(EventBusEventType.FormBuilder.Save, onFormSave);
            eventBus.removeListener(EventBusEventType.FormBuilder.Publish, onFormPublish);
            eventBus.removeListener(EventBusEventType.FormBuilder.OpenTagSelector, openTagSelector);
            document.removeEventListener('blur', onBlurCallback);
        };
    });

    return (
        <div>
            <FormBuilderMenuBar onInsert={onInsert} onAddNewPage={onAddNewPage} onAddFormLogo={onAddFormLogo} onAddFormCover={onAddFormCover} onPreview={onPreview} onFormPublish={onFormPublish} />
            <div className="h-full w-full max-w-4xl mx-auto py-10">
                <div className="flex flex-col gap-4 px-5 md:px-[89px]">
                    {builderTitleAndDescriptionList.map((b: IBuilderTitleAndDescriptionObj) => (
                        <CustomContentEditable
                            key={b.id}
                            id={b.id}
                            tagName={b.tagName}
                            type={b.type}
                            value={builderState[b.key]}
                            position={b.position}
                            placeholder={t(b.placeholder)}
                            className={b.className}
                            onChangeCallback={(event: FormEvent<HTMLElement>) => {
                                if (isUndoRedoInProgress) return;
                                setBackspaceCount(0);
                                dispatch(setBuilderState({ [b.key]: event.currentTarget.innerText }));
                                handleUserTypingEnd();
                            }}
                            onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                                event.preventDefault();
                                setBackspaceCount(0);
                                dispatch(setActiveField({ position: b.position, id: b.id }));
                            }}
                        />
                    ))}
                </div>
                <div ref={builderDragDropRef} className="relative pb-10">
                    <BuilderDragDropContext
                        Component={FormBuilderBlock}
                        componentAttrs={{ setBackspaceCount }}
                        droppableId="form-builder"
                        droppableItems={Object.values(builderState.fields || {})}
                        droppableClassName="pt-10"
                        onDragStartHandlerCallback={(start: DragStart, provided: ResponderProvided) => {}}
                        onDragUpdateHandlerCallback={(update: DragUpdate, provided: ResponderProvided) => {}}
                        onDragEndHandlerCallback={(result: DropResult, provided: ResponderProvided) => {
                            if (!result.destination) {
                                return;
                            }
                            const items: Array<IFormFieldState> = reorder(Object.values(builderState.fields), result.source.index, result.destination.index);
                            batch(() => {
                                dispatch(setFields(items));
                                dispatch(setBuilderState({ activeFieldIndex: result.destination?.index ?? builderState.activeFieldIndex }));
                            });
                        }}
                    />
                    <div
                        className={` absolute w-fit cursor-pointer  px-5  md:px-[89px] flex items-center min-h-[40px] group`}
                        onClick={() => {
                            dispatch(setAddNewField(createNewField(Object.keys(builderState.fields).length - 1)));
                        }}
                    >
                        {getAddFieldPrompt}
                    </div>
                </div>
                <div className="mt-10  px-5 md:px-[89px]">
                    <ContentEditable
                        className="w-fit rounded py-3 px-5 text-white !text-[14px] !font-semibold bg-blue-500 min-w-[130px] text-center focus-visible:border-0 focus-visible:outline-none"
                        html={builderState.buttonText || ''}
                        onKeyDown={(event) => {
                            event.stopPropagation();
                        }}
                        onBlur={(event) => {
                            if (!event.currentTarget.innerText) dispatch(setBuilderState({ buttonText: 'Submit' }));
                        }}
                        onChange={(event: FormEvent<HTMLInputElement>) => {
                            dispatch(setBuilderState({ buttonText: event.currentTarget.innerText }));
                        }}
                    />
                </div>
                {!builderState.isFormDirty && <BuilderTips />}
            </div>
        </div>
    );
}
