import React, { FormEvent, useCallback, useEffect, useRef } from 'react';

import { useRouter } from 'next/router';

import FormBuilderBlock from '@Components/FormBuilder/BuilderBlock';
import BuilderTips from '@Components/FormBuilder/BuilderTips';
import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';
import BuilderDragDropContext from '@Components/FormBuilder/DragDropContext';
import FormBuilderMenuBar from '@Components/FormBuilder/MenuBar';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { DragStart, DragUpdate, DropResult, ResponderProvided } from 'react-beautiful-dnd';
import { batch } from 'react-redux';
import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addDuplicateField, resetBuilderMenuState, setActiveChoice, setAddNewField, setBuilderState, setDeleteField, setFields, setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IBuilderState, IBuilderTitleAndDescriptionObj, IFormFieldState } from '@app/store/form-builder/types';
import { builderTitleAndDescriptionList } from '@app/store/form-builder/utils';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateFormMutation, usePatchFormMutation } from '@app/store/workspaces/api';
import { reorder } from '@app/utils/arrayUtils';
import { createNewField, isMultipleChoice } from '@app/utils/formBuilderBlockUtils';

import useFormBuilderState from './context';

export default function FormBuilder({ workspace, _nextI18Next, isEditMode = false }: { isEditMode?: boolean; workspace: WorkspaceDto; _nextI18Next: any }) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const { t } = useBuilderTranslation();
    const builderDragDropRef = useRef<HTMLDivElement | null>(null);

    const router = useRouter();

    const builderState: IBuilderState = useAppSelector(selectBuilderState);
    const onKeyDownCallbackRef = useRef<any>(null);
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
            fullScreenModal.openModal('FORM_BUILDER_PREVIEW');
        });
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
        publishRequest.fields = fields;
        publishRequest.settings = builderState.settings;
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

    const onFormPublish = async () => {
        const response = await onFormSave(true);
        onFormPublishRedirect(response);
    };

    const throttle = (func: Function, delay: number) => {
        let timeoutId: any;
        return (...args: any[]) => {
            if (!timeoutId) {
                timeoutId = setTimeout(() => {
                    // @ts-ignore
                    func.apply(this, args);
                    timeoutId = null;
                }, delay);
            }
        };
    };

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) => {
            batch(async () => {
                const fieldId = builderState.activeFieldId;
                const formField = builderState.fields[fieldId];

                if (event.key === 'Escape') {
                    dispatch(resetBuilderMenuState());
                }

                if (builderState.menus?.commands?.isOpen || fullScreenModal.isOpen || modal.isOpen || builderState.menus?.spotlightField?.isOpen) {
                    // event.preventDefault();
                    // event.stopPropagation();
                    return;
                }

                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    event.stopPropagation();
                    if (isMultipleChoice(formField.type)) {
                        //@ts-ignore
                        if ((formField.properties?.choices[formField.properties.activeChoiceId].value || '') !== '') {
                            const id = uuidv4();
                            const newChoices = Object.values(formField.properties?.choices || {});
                            newChoices.splice((formField.properties?.activeChoiceIndex ?? 0) + 1, 0, { id, value: '' });
                            const choices: any = {};
                            newChoices.forEach((choice: any) => {
                                choices[choice.id] = choice;
                            });
                            dispatch(setUpdateField({ ...formField, properties: { ...formField.properties, choices: choices } }));
                        } else {
                            const choices = { ...formField.properties?.choices };
                            //@ts-ignore
                            delete choices[formField.properties.activeChoiceId];
                            const newField: IFormFieldState = createNewField(builderState.activeFieldIndex);
                            batch(() => {
                                dispatch(setUpdateField({ ...formField, properties: { ...formField.properties, choices: { ...choices } } }));
                                if (Object.values(choices).length === 0) dispatch(setDeleteField(formField.id));
                                dispatch(setAddNewField(newField));
                                dispatch(
                                    setBuilderState({
                                        isFormDirty: true,
                                        activeFieldIndex: builderState.activeFieldIndex + (Object.values(choices).length === 0 ? 0 : 1)
                                    })
                                );
                            });
                        }
                    } else if (builderState.activeFieldIndex >= -1) {
                        const newField: IFormFieldState = {
                            id: v4(),
                            type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                            isCommandMenuOpen: false,
                            position: builderState.activeFieldIndex
                        };
                        dispatch(setAddNewField(newField));
                        dispatch(
                            setBuilderState({
                                isFormDirty: true,
                                activeFieldIndex: builderState.activeFieldIndex + 1
                            })
                        );
                    }
                }

                if (event.key === 'Tab' || (event.shiftKey && event.key === 'Tab')) event.preventDefault();
                // Only for multiple choice
                if (event.key === 'ArrowDown' && isMultipleChoice(formField.type)) {
                    //@ts-ignore
                    if (formField.properties?.activeChoiceIndex < Object.values(formField.properties?.choices).length - 1) {
                        dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) + 1 }));
                    }
                }
                if (event.key === 'ArrowUp' && isMultipleChoice(formField.type)) {
                    //@ts-ignore
                    if (formField.properties?.activeChoiceIndex > 0) {
                        dispatch(setActiveChoice({ position: (formField.properties?.activeChoiceIndex ?? 0) - 1 }));
                    }
                }
                if (
                    !event.ctrlKey &&
                    !event.metaKey &&
                    (event.key === 'ArrowDown' || (event.key === 'Enter' && builderState.activeFieldIndex < -1)) &&
                    builderState.activeFieldIndex < Object.keys(builderState.fields).length - 1 &&
                    (!isMultipleChoice(formField.type) || formField.properties?.activeChoiceIndex === Object.values(formField.properties?.choices ?? {}).length - 1)
                ) {
                    dispatch(setBuilderState({ activeFieldIndex: builderState.activeFieldIndex + 1 }));
                }
                if (!event.ctrlKey && !event.metaKey && event.key === 'ArrowUp' && builderState.activeFieldIndex > -2 && (!isMultipleChoice(formField.type) || (formField.properties?.activeChoiceIndex ?? 0) === 0)) {
                    dispatch(setBuilderState({ activeFieldIndex: builderState.activeFieldIndex - 1 }));
                }
                if (event.code === 'Slash' && builderState.activeFieldIndex >= 0) {
                    const viewportHeight = window.innerHeight;
                    const bottomPosition = builderDragDropRef.current?.getBoundingClientRect().bottom ?? 0;
                    console.log({
                        viewportHeight,
                        bottomPosition,
                        position: bottomPosition + 300 > viewportHeight ? 'up' : 'down'
                    });
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
                }
                if (event.key === 'Backspace' && (!event.metaKey || !event.ctrlKey) && builderState.activeFieldIndex >= 0) {
                    console.log({ 'backspace count': backspaceCount });
                    console.log('backspace pressed');
                    // TODO: Add support for other input types or form field type as well
                    if (!formField?.value && backspaceCount === 1) {
                        asyncDispatch(setDeleteField(fieldId)).then(() => setBackspaceCount(0));
                        dispatch(setBuilderState({ activeFieldIndex: builderState.activeFieldIndex - 1 }));
                    } else {
                        setBackspaceCount(1);
                    }
                    dispatch(
                        setBuilderState({
                            isFormDirty: true,
                            menus: { ...builderState.menus, commands: { isOpen: false, atFieldUuid: '', position: 'down' } }
                        })
                    );
                }

                if (((event.key === 'Delete' && event.ctrlKey) || (event.key === 'Backspace' && event.metaKey)) && fieldId) {
                    event.preventDefault();
                    event.stopPropagation();

                    if (builderState.activeFieldIndex < 0) {
                        toast("Can't delete the form title and description", { type: 'warning' });
                    } else dispatch(setDeleteField(fieldId));
                    dispatch(
                        setBuilderState({
                            isFormDirty: true,
                            activeFieldIndex: builderState.activeFieldIndex > 0 ? builderState.activeFieldIndex - 1 : 0
                        })
                    );
                }
                if ((event.key === 'D' || event.key === 'd') && !event.shiftKey && (event.ctrlKey || event.metaKey) && fieldId) {
                    event.preventDefault();
                    event.stopPropagation();
                    if (builderState.activeFieldIndex < 0) {
                        toast("Can't duplicate the form title and description", { type: 'warning' });
                    } else {
                        const formField = builderState.fields[fieldId];
                        const newField: IFormFieldState = { ...formField };
                        newField.id = v4();
                        newField.position = builderState.activeFieldIndex + 1;
                        dispatch(addDuplicateField(newField));
                        dispatch(setBuilderState({ isFormDirty: true }));
                    }
                }
                if ((event.key === 'I' || event.key === 'i') && !event.shiftKey && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    event.stopPropagation();
                    onInsert();
                }
                if ((event.key === 'S' || event.key === 's') && !event.shiftKey && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    event.stopPropagation();
                    await onFormSave();
                }
                if ((event.key === 'P' || event.key === 'p') && !event.shiftKey && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    event.stopPropagation();
                    onPreview();
                }
            });
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [builderState, backspaceCount]
    );

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

    useEffect(() => {
        onKeyDownCallbackRef.current = throttle(onKeyDownCallback, 100);

        onBlurCallbackRef.current = throttle(onBlurCallback, 100);
        document.addEventListener('keydown', onKeyDownCallback);
        document.addEventListener('blur', onBlurCallback);

        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
            document.removeEventListener('blur', onBlurCallback);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [builderState, onKeyDownCallback, onBlurCallback]);

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
                            activeFieldIndex={builderState.activeFieldIndex}
                            placeholder={t(b.placeholder)}
                            className={b.className}
                            onChangeCallback={(event: FormEvent<HTMLElement>) => {
                                setBackspaceCount(0);
                                dispatch(setBuilderState({ isFormDirty: true, [b.key]: event.currentTarget.innerText }));
                            }}
                            onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                                event.preventDefault();
                                setBackspaceCount(0);
                                dispatch(setBuilderState({ activeFieldIndex: b.position }));
                            }}
                        />
                    ))}
                </div>
                <div ref={builderDragDropRef}>
                    <BuilderDragDropContext
                        Component={FormBuilderBlock}
                        componentAttrs={{ setBackspaceCount }}
                        droppableId="form-builder"
                        droppableItems={Object.values(builderState.fields || {})}
                        droppableClassName="py-10"
                        onDragStartHandlerCallback={(start: DragStart, provided: ResponderProvided) => {}}
                        onDragUpdateHandlerCallback={(update: DragUpdate, provided: ResponderProvided) => {}}
                        onDragEndHandlerCallback={(result: DropResult, provided: ResponderProvided) => {
                            if (!result.destination?.index) {
                                return;
                            }
                            const items: Array<IFormFieldState> = reorder(Object.values(builderState.fields), result.source.index, result.destination.index);
                            batch(() => {
                                dispatch(setFields(items));
                                dispatch(setBuilderState({ activeFieldIndex: result.destination?.index ?? builderState.activeFieldIndex }));
                            });
                        }}
                    />
                </div>
                <BuilderTips />
            </div>
        </div>
    );
}
