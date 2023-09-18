import React, { FormEvent, HTMLAttributes, MouseEventHandler, useCallback, useEffect, useRef, useState } from 'react';

import { useRouter } from 'next/router';

import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock';
import BuilderTips from '@Components/FormBuilder/BuilderTips';
import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';
import BuilderDragDropContext from '@Components/FormBuilder/DragDropContext';
import { FormCoverComponent, FormLogoComponent } from '@Components/FormBuilder/Header';
import MarkdownEditor from '@Components/FormBuilder/MarkdownEditor';
import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import useFormBuilderAtom from '@Components/FormBuilder/builderAtom';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { SetStateAction } from 'jotai';
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
import { ResponseRetentionType } from '@app/models/enums/consentEnum';
import EventBusEventType from '@app/models/enums/eventBusEnum';
import { resetConsentState } from '@app/store/consent/actions';
import { selectConsentState } from '@app/store/consent/selectors';
import { IConsentField, IConsentState } from '@app/store/consent/types';
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
    const { openModal } = useFullScreenModal();
    const { openModal: openHalfScreenModal } = useModal();
    const { t } = useBuilderTranslation();
    const { handleUserTypingEnd } = useUserTypingDetection();
    const { isUndoRedoInProgress } = useUndoRedo();
    const builderDragDropRef = useRef<HTMLDivElement | null>(null);

    const router = useRouter();
    const builderState: IBuilderState = useAppSelector(selectBuilderState);
    const consentState: IConsentState = useAppSelector(selectConsentState);

    const [showLogo, setShowLogo] = useState(false);
    const [showCover, setShowCover] = useState(false);

    const onBlurCallbackRef = useRef<any>(null);
    const { headerImages, resetImages } = useFormBuilderAtom();

    const { backspaceCount, setBackspaceCount } = useFormBuilderState();

    const [postCreateForm, { isLoading: posting }] = useCreateFormMutation();
    const [patchForm, { isLoading: patching }] = usePatchFormMutation();

    const [imagesRemoved, setImagesRemoved] = useState<{ logo: boolean; cover: boolean }>({ logo: false, cover: false });

    const fullScreenModal = useFullScreenModal();
    const modal = useModal();
    //
    const locale = _nextI18Next.initialLocale === 'en' ? '' : `${_nextI18Next.initialLocale}/`;

    useEffect(() => {
        setShowLogo(!!builderState.logo);
        setShowCover(!!builderState.coverImage);
    }, [builderState.logo, builderState.coverImage]);

    const onInsert = () => {
        asyncDispatch(resetBuilderMenuState()).then(() => {
            modal.openModal('FORM_BUILDER_ADD_FIELD_VIEW');
        });
    };

    const onAddNewPage = () => {};

    const onAddFormLogo = () => {
        setShowLogo(true);
    };

    const onAddFormCover = () => {
        setShowCover(true);
    };

    const onPreview = () => {
        asyncDispatch(resetBuilderMenuState()).then(() => {
            fullScreenModal.openModal('FORM_BUILDER_PREVIEW', { publish: onFormPublish });
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

    const onFormSave = async (isPublishClicked = false, consent: IConsentField[] = [], privacyPolicyUrl = '', responseExpiration = '', responseExpirationType: ResponseRetentionType = 'forever') => {
        const apiCall = !isEditMode ? postCreateForm : patchForm;

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
            privacyPolicyUrl: privacyPolicyUrl,
            responseExpiration: responseExpiration,
            responseExpirationType: responseExpirationType
        };
        debugger;
        publishRequest.buttonText = builderState.buttonText;
        publishRequest.consent = consent;
        if (imagesRemoved.logo) publishRequest.logo = '';
        if (imagesRemoved.cover) publishRequest.cover_image = '';
        formData.append('form_body', JSON.stringify(publishRequest));
        const apiObj: any = { workspaceId: workspace.id, body: formData };
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
        if (!isEditMode) {
            const onFormPublishCallback = async ({
                consent,
                privacyPolicyUrl = '',
                responseExpirationType,
                responseExpiration
            }: {
                consent: IConsentField[];
                privacyPolicyUrl?: string;
                responseExpirationType?: ResponseRetentionType;
                responseExpiration?: string;
            }) => {
                const response = await onFormSave(true, consent, privacyPolicyUrl, responseExpiration, responseExpirationType);
                onFormPublishRedirect(response);
            };
            openModal('CREATE_CONSENT_FULL_MODAL_VIEW', { onFormPublish: onFormPublishCallback });
        } else {
            const response = await onFormSave(true);
            onFormPublishRedirect(response);
        }
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
            <div className="h-10 group-hover:h-0"></div>
            <div className="lg:invisible py-2 px-4 bg-gray-50 font-medium text-gray-400 rounded-md text-sm group-hover:visible">Click to add new field</div>
        </>
    );

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

    return (
        <div>
            <FormBuilderMenuBar
                onInsert={onInsert}
                onAddNewPage={onAddNewPage}
                onAddFormLogo={onAddFormLogo}
                onAddFormCover={onAddFormCover}
                onPreview={onPreview}
                onFormPublish={onFormPublish}
                onClickSettings={onClickSettings}
                onClickTips={onClickTips}
                isUpdating={posting || patching}
            />
            {showCover && <FormCoverComponent setIsCoverClicked={setShowCover} imagesRemoved={imagesRemoved} setImagesRemoved={setImagesRemoved} />}
            <div className="h-full w-full max-w-4xl mx-auto py-10">
                {showLogo && <FormLogoComponent setIsLogoClicked={setShowLogo} className={showCover ? '-mt-[90px]' : ''} imagesRemoved={imagesRemoved} setImagesRemoved={setImagesRemoved} />}
                <div className="flex flex-col gap-2 px-5 md:px-[89px]">
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
                        droppableClassName="pt-8"
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
                        className={` absolute w-fit cursor-pointer  px-12  md:px-[89px] flex items-center min-h-[40px] group`}
                        onClick={() => {
                            dispatch(setAddNewField(createNewField(Object.keys(builderState.fields).length - 1)));
                        }}
                    >
                        {getAddFieldPrompt}
                    </div>
                </div>
                <div className="mt-2  px-12 md:px-[89px]">
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
            </div>
        </div>
    );
}
