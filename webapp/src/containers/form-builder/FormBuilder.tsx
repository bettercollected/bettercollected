import React, { FormEvent, useCallback, useEffect, useRef, useState } from 'react';

import { useRouter } from 'next/router';

import _ from 'lodash';

import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock';
import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';
import BuilderDragDropContext from '@Components/FormBuilder/DragDropContext';
import { FormCoverComponent, FormLogoComponent } from '@Components/FormBuilder/Header';
import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import useFormBuilderAtom from '@Components/FormBuilder/builderAtom';
import { Check } from '@mui/icons-material';
import { CircularProgress } from '@mui/material';
import { AnimatePresence, motion } from 'framer-motion';
import { DragStart, DragUpdate, DropResult, ResponderProvided } from 'react-beautiful-dnd';
import ContentEditable from 'react-contenteditable';
import { batch } from 'react-redux';

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
import { resetBuilderMenuState, setActiveField, setAddNewField, setBuilderState, setFields } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IBuilderTitleAndDescriptionObj, IFormFieldState } from '@app/store/form-builder/types';
import { builderTitleAndDescriptionList } from '@app/store/form-builder/utils';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormMutation } from '@app/store/workspaces/api';
import { reorder } from '@app/utils/arrayUtils';
import { createNewField } from '@app/utils/formBuilderBlockUtils';
import { throttle } from '@app/utils/throttleUtils';

import useFormBuilderState from './context';

export default function FormBuilder({ workspace, _nextI18Next }: { workspace: WorkspaceDto; _nextI18Next: any }) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const { openModal } = useFullScreenModal();
    const { openModal: openHalfScreenModal } = useModal();
    const { t } = useBuilderTranslation();
    const { handleUserTypingEnd } = useUserTypingDetection();
    const { isUndoRedoInProgress } = useUndoRedo();
    const builderDragDropRef = useRef<HTMLDivElement | null>(null);
    const consentState = useAppSelector(selectConsentState);
    const router = useRouter();

    const { form_id } = router.query;
    const builderState: IBuilderState = useAppSelector(selectBuilderState);

    const [showLogo, setShowLogo] = useState(false);
    const [showCover, setShowCover] = useState(false);

    const onBlurCallbackRef = useRef<any>(null);
    const { headerImages, resetImages } = useFormBuilderAtom();

    const { backspaceCount, setBackspaceCount } = useFormBuilderState();

    const [patchForm, { isLoading: patching }] = usePatchFormMutation();

    const [imagesRemoved, setImagesRemoved] = useState<{ logo: boolean; cover: boolean }>({ logo: false, cover: false });

    const fullScreenModal = useFullScreenModal();
    const modal = useModal();

    const [showSaving, setShowSaving] = useState({ status: false, text: 'Saving' });

    //

    useEffect(() => {
        setShowLogo(!!builderState.logo);
        setShowCover(!!builderState.coverImage);
    }, [builderState.logo, builderState.coverImage]);

    const onInsert = () => {
        asyncDispatch(resetBuilderMenuState()).then(() => {
            modal.openModal('FORM_BUILDER_ADD_FIELD_VIEW');
        });
    };

    const onAddFormLogo = () => {
        setShowLogo(true);
    };

    const onAddFormCover = () => {
        setShowCover(true);
    };

    const onPreview = () => {
        asyncDispatch(resetBuilderMenuState()).then(() => {
            fullScreenModal.openModal('FORM_BUILDER_PREVIEW', { publish: onFormPublish, imagesRemoved });
        });
    };

    const onClickSettings = () => {
        openModal('FORM_SETTINGS_FULL_MODAL_VIEW');
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
        fields = fields.map((field: IFormFieldState) => {
            if (field.properties?.choices) {
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
        publishRequest.buttonText = builderState.buttonText;
        publishRequest.consent = consentState.consents;
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

    const saveFormDebounced = useCallback(
        _.debounce((builderState, consentState, headerImages) => onFormSave(builderState, consentState, headerImages), 2000),
        []
    );

    useEffect(() => {
        setShowSaving({ status: true, text: 'Saving' });
        saveFormDebounced(builderState, consentState, headerImages);
    }, [builderState.id, builderState.fields, builderState.title, builderState.description, builderState.buttonText, headerImages, consentState, imagesRemoved]);

    const openTagSelector = (event: any) => {
        const viewportHeight = window.innerHeight;
        const boundingRect = event.target.getBoundingClientRect();
        const bottomPosition = boundingRect.bottom ?? 0;

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

        return () => {
            eventBus.removeListener(EventBusEventType.FormBuilder.Preview, onPreview);
            eventBus.removeListener(EventBusEventType.FormBuilder.OpenTagSelector, openTagSelector);
            document.removeEventListener('blur', onBlurCallback);
        };
    }, [builderState]);

    const isLastFieldEmptyTextField = () => {
        const fields = Object.values(builderState.fields);
        const lastField = fields[fields.length - 1];

        if (lastField.type === FormBuilderTagNames.LAYOUT_SHORT_TEXT && !lastField.value) return true;
    };

    return (
        <div>
            <FormBuilderMenuBar
                onInsert={onInsert}
                onAddNewPage={() => {}}
                onAddFormLogo={onAddFormLogo}
                onAddFormCover={onAddFormCover}
                onPreview={onPreview}
                onFormPublish={onFormPublish}
                onClickSettings={onClickSettings}
                onClickTips={onClickTips}
                isUpdating={patching}
            />
            {showCover && <FormCoverComponent setIsCoverClicked={setShowCover} imagesRemoved={imagesRemoved} setImagesRemoved={setImagesRemoved} />}
            <div className="h-full w-full max-w-4xl mx-auto py-12">
                {showLogo && <FormLogoComponent setIsLogoClicked={setShowLogo} className={showCover ? '-mt-[90px]' : ''} imagesRemoved={imagesRemoved} setImagesRemoved={setImagesRemoved} />}
                <div className="flex flex-col gap-2 px-12 md:px-[89px]">
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
