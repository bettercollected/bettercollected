import cn from 'classnames';
import styled from 'styled-components';

import { FormSlideLayout } from '@app/models/enums/form';
import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import { Button } from '@app/shadcn/components/ui/button';
import { useFormState } from '@app/store/jotai/form';

import GreetingLayoutWrapper from '../Layout/GreetingLayoutWrapper';
import { useEffect, useState } from 'react';
import { useDebounceValue } from 'usehooks-ts';

const StyledInputField = styled.input`
    &::placeholder {
        color: #aeb9d8;
    }
`;

const WelcomeSlide = ({ disabled }: { disabled?: boolean }) => {
    const { theme, formState, setFormDescription, setWelcomeTitle } = useFormState();
    const [description, setDescription] = useState('');
    const [debouncedDescription] = useDebounceValue(description, 300);
    useEffect(() => {
        formState?.welcomePage?.description && setDescription(formState?.welcomePage?.description);
    }, [formState?.welcomePage?.description]);
    useEffect(() => {
        setFormDescription(debouncedDescription);
    }, [debouncedDescription]);

    return (
        <GreetingLayoutWrapper theme={theme} disabled={disabled} greetingIndex={-10}>
            <div className={cn('flex h-full flex-col justify-center bg-transparent', formState.welcomePage?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? ' items-start' : ' items-center')}>
                <div className={cn('flex w-full max-w-[800px] flex-col items-start')}>
                    <AutosizeTextarea
                        style={{ resize: 'none' }}
                        placeholder="Form Title"
                        className=" w-full border-0 px-0 py-0 text-[40px] font-bold leading-[60px]"
                        value={formState.welcomePage?.title}
                        onChange={(event) => {
                            setWelcomeTitle(event.target.value);
                        }}
                    />
                    {formState?.welcomePage?.description !== undefined && formState?.welcomePage?.description !== null ? (
                        <>
                            <AutosizeTextarea
                                placeholder="Add description"
                                style={{ resize: 'none' }}
                                value={description}
                                className="ring-none text-black-600 mb-4 w-full border-0 px-0 text-base outline-none"
                                onChange={(e: any) => setDescription(e.target.value)}
                            />
                        </>
                    ) : (
                        <></>
                    )}
                    <Button size={'medium'} className="z-10 mt-12 rounded px-8 py-3" style={{ background: theme?.secondary }}>
                        {formState.welcomePage?.buttonText || 'Start'}
                    </Button>
                </div>
            </div>
        </GreetingLayoutWrapper>
    );
};

export default WelcomeSlide;
