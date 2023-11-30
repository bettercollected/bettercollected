import React, { FormEvent, useCallback, useEffect, useRef, useState } from 'react';

import { useRouter } from 'next/router';

import _ from 'lodash';

import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock';
import BuilderTips from '@Components/FormBuilder/BuilderTips';
import BuilderDragDropContext from '@Components/FormBuilder/DragDropContext';
import { FormCoverComponent, FormLogoComponent } from '@Components/FormBuilder/Header';
import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import FormBuilderTitleDescriptionInput from '@Components/FormBuilder/TitleAndDescription/FormBuilderTitleDescriptionInput';
import useFormBuilderAtom from '@Components/FormBuilder/builderAtom';
import { Check } from '@mui/icons-material';
import { CircularProgress } from '@mui/material';
import { AnimatePresence, motion } from 'framer-motion';
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
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { selectConsentState } from '@app/store/consent/selectors';
import { resetBuilderMenuState, setActiveField, setAddNewField, setBuilderMenuState, setBuilderState, setFields } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IBuilderTitleAndDescriptionObj, IFormFieldState } from '@app/store/form-builder/types';
import { builderTitleAndDescriptionList } from '@app/store/form-builder/utils';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { updateStatus } from '@app/store/mutations/slice';
import { usePatchTemplateMutation } from '@app/store/template/api';
import { usePatchFormMutation } from '@app/store/workspaces/api';
import { reorder } from '@app/utils/arrayUtils';
import { createNewField } from '@app/utils/formBuilderBlockUtils';
import { throttle } from '@app/utils/throttleUtils';

import useFormBuilderState from './context';

export default function FormBuilder({ workspace, _nextI18Next, isTemplate = false, templateId }: { workspace: WorkspaceDto; _nextI18Next: any; isTemplate?: boolean; templateId?: string }) {
    // Hooks
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const builderDragDropRef = useRef<HTMLDivElement | null>(null);
    const router = useRouter();

    // Modals
    const { openModal } = useFullScreenModal();
    const { openModal: openHalfScreenModal } = useModal();
    const fullScreenModal = useFullScreenModal();

    // Translation
    const { t } = useBuilderTranslation();

    // User Interaction
    const { handleUserTypingEnd } = useUserTypingDetection();
    const { isUndoRedoInProgress } = useUndoRedo();

    // Selectors and State
    const consentState = useAppSelector(selectConsentState);
    const builderState: IBuilderState = useAppSelector(selectBuilderState);
    const { form_id } = router.query;

    // Form Builder State
    const { backspaceCount, setBackspaceCount } = useFormBuilderState();
    const { headerImages, resetImages } = useFormBuilderAtom();

    // Saving State
    const [patchForm, { isLoading: patching }] = usePatchFormMutation();
    const [showSaving, setShowSaving] = useState({ status: false, text: 'Saving' });

    // Display State
    const [showLogo, setShowLogo] = useState(false);
    const [showCover, setShowCover] = useState(false);
    const [imagesRemoved, setImagesRemoved] = useState<{ logo: boolean; cover: boolean }>({ logo: false, cover: false });

    // Callbacks and Refs
    const onBlurCallbackRef = useRef<any>(null);
    //

    // RTK
    const [updateTemplate] = usePatchTemplateMutation();

    useEffect(() => {
        setShowLogo(!!builderState.logo);
        setShowCover(!!builderState.coverImage);
    }, [builderState.logo, builderState.coverImage]);

    const onAddFormLogo = () => {
        setShowLogo(true);
    };

    const onAddFormCover = () => {
        setShowCover(true);
    };

    const onPreview = () => {
        asyncDispatch(resetBuilderMenuState()).then(() => {
            fullScreenModal.openModal('FORM_BUILDER_PREVIEW', { publish: onFormPublish, imagesRemoved, isTemplate });
        });
    };

    const onClickTips = () => {
        openHalfScreenModal('FORM_BUILDER_TIPS_MODAL_VIEW');
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

    const onFormPublish = () => {
        openModal('CREATE_CONSENT_FULL_MODAL_VIEW');
    };

    const onFormSave = async (builderState: any, consentState: any, headerImages: any) => {
        const formData = new FormData();
        if (headerImages.coverImage) formData.append('cover_image', headerImages.coverImage);
        if (headerImages.logo) formData.append('logo', headerImages.logo);

        const publishRequest: any = {};
        publishRequest.title = builderState.title;
        publishRequest.description = builderState.description;
        let fields: any = Object.values(builderState.fields || {});
        // TODO extract this to a function
        fields = fields.map((field: IFormFieldState) => {
            if (field?.type == FormBuilderTagNames.CONDITIONAL) {
                return {
                    ...field,
                    properties: {
                        ...field.properties,
                        conditions: Object.values(field.properties?.conditions || {}),
                        actions: Object.values(field.properties?.actions || {})
                    }
                };
            } else if (field.properties?.choices) {
                return { ...field, properties: { ...field.properties, choices: Object.values(field.properties?.choices) } };
            }
            return field;
        });
        publishRequest.fields = fields;
        publishRequest.settings = {
            ...builderState.settings,
            privacyPolicyUrl: consentState.privacyPolicyUrl,
            responseExpiration: consentState.responseExpiration,
            responseExpirationType: consentState.responseExpirationType
        };
        publishRequest.consent = consentState.consents;
        publishRequest.buttonText = builderState.buttonText;
        if (imagesRemoved.logo) publishRequest.logo = '';
        if (imagesRemoved.cover) publishRequest.cover_image = '';
        formData.append('form_body', JSON.stringify(publishRequest));
        const apiObj: any = { formId: form_id, workspaceId: workspace.id, body: formData };
        const response: any = await patchForm(apiObj);
        if (response?.data) {
            setShowSaving({ status: true, text: 'Saved' });
            setTimeout(() => {
                setShowSaving({ status: false, text: 'Saving' });
            }, 1500);
        }
    };

    const onSaveTemplate = async () => {
        dispatch(updateStatus({ endpoint: 'patchTemplate', status: 'loading' }));
        const templateData = new FormData();
        if (headerImages.coverImage) templateData.append('cover_image', headerImages.coverImage);
        if (headerImages.logo) templateData.append('logo', headerImages.logo);
        const publishRequest: any = {};
        publishRequest.title = builderState.title;
        publishRequest.description = builderState.description;
        let fields: any = Object.values(builderState.fields || {});
        fields = fields.map((field: IFormFieldState) => {
            if (field?.type == FormBuilderTagNames.CONDITIONAL) {
                return {
                    ...field,
                    properties: {
                        ...field.properties,
                        conditions: Object.values(field.properties?.conditions || {}),
                        actions: Object.values(field.properties?.actions || {})
                    }
                };
            } else if (field.properties?.choices) {
                return { ...field, properties: { ...field.properties, choices: Object.values(field.properties?.choices) } };
            }
            return field;
        });
        publishRequest.fields = fields;
        publishRequest.buttonText = builderState.buttonText;
        if (imagesRemoved.logo) publishRequest.logo = '';
        if (imagesRemoved.cover) publishRequest.cover_image = '';
        templateData.append('template_body', JSON.stringify(publishRequest));
        const apiObj: any = { template_id: templateId, workspace_id: workspace.id, body: templateData };
        try {
            const response: any = await updateTemplate(apiObj);
            if (response?.data) {
                dispatch(updateStatus({ endpoint: 'patchTemplate', status: 'success' }));
                toast('Successful', { type: 'success' });
                await router.replace(`/${workspace.workspaceName}/dashboard/templates`);
            } else {
                dispatch(updateStatus({ endpoint: 'patchTemplate', status: 'failed' }));

                toast('Error Occurred').toString(), { type: 'error' };
            }
        } catch (err) {
            dispatch(updateStatus({ endpoint: 'patchTemplate', status: 'failed' }));

            toast('Error Occurred').toString(), { type: 'error' };
        }
    };

    const saveFormDebounced = useCallback(
        _.debounce((builderState, consentState, headerImages) => onFormSave(builderState, consentState, headerImages), 2000),
        []
    );

    useEffect(() => {
        if (!isTemplate) {
            setShowSaving({ status: true, text: 'Saving' });
            saveFormDebounced(builderState, consentState, headerImages);
        }
    }, [builderState.id, builderState.fields, builderState.title, builderState.description, builderState.buttonText, headerImages, consentState, imagesRemoved, builderState.settings]);

    const openMenu = (event: any, menuType: string) => {
        const viewportHeight = window.innerHeight;
        const boundingRect = event.target.getBoundingClientRect();
        const bottomPosition = boundingRect.bottom ?? 0;

        const getPosition = () => {
            const selection: any = window.getSelection();
            if (selection && selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                if (range) {
                    const rects = range.getClientRects();
                    if (rects.length > 0) {
                        return { top: rects[0].top, left: rects[0].left };
                    }
                }
            }
            return {
                top: boundingRect.top,
                left: boundingRect.left
            };
        };

        const value = builderState.fields[builderState.activeFieldId]?.value || '';
        const selection = window.getSelection();

        const cursorPosition = selection?.focusOffset;

        const textBeforeCursor = value.substring(0, cursorPosition);

        const occurrence = (textBeforeCursor.match(/@/g) || []).length + 1;

        dispatch(
            setBuilderState({
                isFormDirty: true,
                menus: {
                    ...builderState.menus,
                    [menuType]: {
                        isOpen: true,
                        atFieldUuid: Object.keys(builderState.fields).at(builderState.activeFieldIndex) ?? '',
                        position: bottomPosition + 300 > viewportHeight ? 'up' : 'down',
                        pos: getPosition(),
                        atPosition: occurrence ?? 0
                    }
                }
            })
        );
    };

    const openTagSelector = (event: any) => {
        openMenu(event, 'commands');
    };

    const openFieldSelector = (event: any) => {
        openMenu(event, 'pipingFields');
    };

    function onClickMentionElement(event: Event) {
        event.stopPropagation();
        event.preventDefault();
        const targetElement = event.target as HTMLElement;
        const mentionedFieldId = targetElement.getAttribute('data-field-id');
        const currentField = targetElement.getAttribute('data-current-field');

        const boundingRect = targetElement.getBoundingClientRect();

        dispatch(
            setBuilderMenuState({
                pipingFieldSettings: {
                    isOpen: true,
                    atFieldId: currentField || '',
                    mentionedFieldId: mentionedFieldId || '',
                    pos: { top: boundingRect.top, left: boundingRect.left }
                }
            })
        );
    }

    useEffect(() => {
        resetImages();
        return () => {
            resetImages();
        };
    }, []);

    useEffect(() => {
        onBlurCallbackRef.current = throttle(onBlurCallback, 100);
        document.addEventListener('blur', onBlurCallback);

        // Listens events from the HOCs
        eventBus.on(EventBusEventType.FormBuilder.Preview, onPreview);
        eventBus.on(EventBusEventType.FormBuilder.OpenTagSelector, openTagSelector);
        eventBus.on(EventBusEventType.FormBuilder.OpenFieldSelector, openFieldSelector);

        document.querySelectorAll('[data-field-id]').forEach((element: Element) => {
            element.addEventListener('click', onClickMentionElement);
        });

        return () => {
            eventBus.removeListener(EventBusEventType.FormBuilder.Preview, onPreview);
            eventBus.removeListener(EventBusEventType.FormBuilder.OpenTagSelector, openTagSelector);
            eventBus.removeListener(EventBusEventType.FormBuilder.OpenFieldSelector, openFieldSelector);
            document.removeEventListener('blur', onBlurCallback);
            document.querySelectorAll('[data-field-id]').forEach((element: Element) => {
                element.removeEventListener('click', onClickMentionElement);
            });
        };
    }, [builderState]);

    useEffect(() => {
        setBackspaceCount(0);
    }, [builderState.activeFieldId, builderState.activeChoiceId]);

    const isLastFieldEmptyTextField = () => {
        const fields = Object.values(builderState.fields);
        const lastField = fields[fields.length - 1];

        if (lastField?.type === FormBuilderTagNames.LAYOUT_SHORT_TEXT && !lastField.value) return true;
    };

    const onTitleDescriptionChangeCallback = (event: FormEvent<HTMLElement>, b: IBuilderTitleAndDescriptionObj) => {
        if (isUndoRedoInProgress) return;
        setBackspaceCount(0);
        dispatch(setBuilderState({ [b.key]: event.currentTarget.innerText }));
        handleUserTypingEnd();
    };

    const onTitleDescriptionFocusCallback = (event: React.FocusEvent<HTMLElement>, b: IBuilderTitleAndDescriptionObj) => {
        event.preventDefault();
        setBackspaceCount(0);
        dispatch(setActiveField({ position: b.position, id: b.id }));
    };

    return (
        <div>
            <FormBuilderMenuBar
                onAddNewPage={() => {}}
                onAddFormLogo={onAddFormLogo}
                onAddFormCover={onAddFormCover}
                onPreview={onPreview}
                onFormPublish={onFormPublish}
                onClickTips={onClickTips}
                isUpdating={patching}
                isTemplate={isTemplate}
                onSaveTemplate={onSaveTemplate}
            />
            {showCover && <FormCoverComponent setIsCoverClicked={setShowCover} imagesRemoved={imagesRemoved} setImagesRemoved={setImagesRemoved} />}
            <div className="h-full w-full max-w-4xl mx-auto py-12">
                {showLogo && <FormLogoComponent setIsLogoClicked={setShowLogo} className={showCover ? '-mt-[90px]' : ''} imagesRemoved={imagesRemoved} setImagesRemoved={setImagesRemoved} />}
                <div className="flex flex-col gap-2 px-12 md:px-[89px]">
                    {builderTitleAndDescriptionList.map((b: IBuilderTitleAndDescriptionObj) => (
                        <FormBuilderTitleDescriptionInput key={b.id} b={b} value={builderState[b.key]} onChangeCallback={onTitleDescriptionChangeCallback} onFocusCallback={onTitleDescriptionFocusCallback} />
                    ))}
                </div>
                <div ref={builderDragDropRef} className="relative">
                    <BuilderDragDropContext
                        Component={FormBuilderBlock}
                        componentAttrs={{ setBackspaceCount }}
                        droppableId="form-builder"
                        droppableItems={Object.values(builderState.fields || {})}
                        droppableClassName="pt-6"
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
                    {!isLastFieldEmptyTextField() ? (
                        <div
                            className={`w-full px-12 md:px-[89px] -mt-[2px] flex min-h-[40px] items-center group`}
                            onClick={() => {
                                batch(() => {
                                    const newField = createNewField(Object.keys(builderState.fields).length - 1);
                                    asyncDispatch(setAddNewField(newField)).then(() => {
                                        document.getElementById('item-' + newField.id)?.focus();
                                    });
                                });
                            }}
                        >
                            <div className="text-sm text-white hover:text-black-600 !w-full flex items-center relative h-full  !cursor-text ">
                                {'   '}
                                <DragHandleIcon className="flex md:hidden group-hover:flex absolute -top-0.5 add-field-drag-icon text-black-800 lg:text-black-600" width={24} height={24} />
                            </div>
                        </div>
                    ) : (
                        <div className="h-10" />
                    )}
                </div>
                <div className="mt-2 px-12 md:px-[89px]">
                    <ContentEditable
                        className="w-fit rounded py-3 px-5 text-white !text-[14px] !font-semibold bg-black-900 min-w-[130px] text-center focus-visible:border-0 focus-visible:outline-none"
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
                <AnimatePresence mode="wait" initial={false}>
                    {showSaving.status && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{
                                ease: 'linear',
                                duration: 0.5,
                                x: { duration: 0.5 }
                            }}
                        >
                            <div className="fixed px-5 py-2 rounded  bg-black-200 text-black-800 bottom-5 right-5 flex justify-center w-[120px] gap-2 lg:bottom-10 lg:right-10">
                                {showSaving.text === 'Saving' ? <CircularProgress size={24} /> : <Check className="text-green-500" height={24} width={24} />}
                                {showSaving.text}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}
