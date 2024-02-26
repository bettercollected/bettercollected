import { useEffect, useRef } from 'react';

import { allowedInputTags, allowedLayoutTags, allowedQuestionAndAnswerTags } from '@Components/FormBuilder/BuilderBlock/FormBuilderTagSelector';
import { Autocomplete, Paper, TextField, styled } from '@mui/material';
import { batch } from 'react-redux';
import { v4 } from 'uuid';

import { useModal } from '@app/components/modal-views/context';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { BlockTypes, FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { resetBuilderMenuState, setAddNewField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';


const GroupHeader = styled('div')(({ theme }) => ({
    position: 'sticky',
    top: '-8px',
    padding: '8px 16px',
    color: '#000000',
    fontWeight: 600,
    textTransform: 'uppercase',
    backgroundColor: '#ffffff'
}));

const GroupItems = styled('ul')(({ theme }) => ({
    padding: 0,
    color: theme.palette.text.primary,
    backgroundColor: theme.palette.secondary.contrastText
}));

interface IField {
    id: FormBuilderTagNames;
    type: FormBuilderTagNames;
    label: string;
    icon: JSX.Element;
    blockType: BlockTypes;
}

const defaultFields = [...allowedLayoutTags, ...allowedInputTags, ...allowedQuestionAndAnswerTags];

export default function FormBuilderSpotlightModal({ index }: { index?: number }) {
    const { closeModal, modalProps } = useModal();

    const { t } = useBuilderTranslation();

    const inputRef = useRef<HTMLInputElement>(null);
    const dispatch = useAppDispatch();

    const builderState = useAppSelector(selectBuilderState);
    const handleFieldSelected = (selected: IField | null) => {
        if (!selected) return;
        batch(() => {
            dispatch(
                setAddNewField({
                    id: v4(),
                    type: selected.type,
                    position: builderState.activeFieldIndex >= 0 ? builderState.activeFieldIndex : Object.keys(builderState.fields).length - 1
                })
            );
            dispatch(resetBuilderMenuState());
        });

        closeModal();
    };

    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.focus();
        }
    }, []);

    return (
        <div className="px-5 py-3 md:px-10 md:py-6 bg-white text-black-800 relative rounded-[4px] w-full md:max-w-[500px] min-h-52 flex flex-col justify-between">
            <Autocomplete
                id="search-fields"
                options={defaultFields}
                groupBy={(option) => option.blockType}
                getOptionLabel={(option) => option.label}
                sx={{
                    minWidth: 300,
                    maxWidth: '100%'
                }}
                PaperComponent={(props) => (
                    <Paper
                        sx={{
                            background: 'white',
                            borderTopLeftRadius: 0,
                            borderTopRightRadius: 0,
                            borderBottomRightRadius: 8,
                            borderBottomLeftRadius: 8
                        }}
                        {...props}
                    />
                )}
                size="medium"
                fullWidth
                disablePortal
                onChange={(_, value) => handleFieldSelected(value)}
                renderInput={(params) => (
                    <TextField
                        {...params}
                        variant="standard"
                        inputMode="text"
                        InputProps={{
                            ...params.InputProps,
                            sx: {
                                paddingLeft: 0,
                                paddingRight: 0,
                                paddingTop: 0,
                                paddingBottom: 0,
                                height: 40,
                                fontSize: 16,
                                fontWeight: 400,
                                color: 'black',
                                content: 'none',
                                borderColor: 'white'
                            }
                        }}
                        inputRef={inputRef}
                        placeholder={t('SPOTLIGHT.PLACEHOLDER')}
                        fullWidth
                    />
                )}
                renderGroup={(params) => (
                    <li key={params.key} className="">
                        <GroupHeader className="font-bold tracking-widest shadow-sm border-b-[1px] border-b-black-400">{params.group}</GroupHeader>
                        <GroupItems>{params.children}</GroupItems>
                    </li>
                )}
            />
            <div className="text-neutral-500 mt-4 text-xs flex flex-col items-start justify-start gap-3">
                <span className="bg-brand-500 rounded-3xl px-2 py-1 font-semibold uppercase leading-none text-white">{t('TIPS.DEFAULT')}</span>
                <ol className="flex flex-col gap-2 list-inside list-decimal">
                    <li className="">{t('SPOTLIGHT.TIPS.1')}</li>
                    <li className="">{t('SPOTLIGHT.TIPS.2')}</li>
                </ol>
            </div>
        </div>
    );
}