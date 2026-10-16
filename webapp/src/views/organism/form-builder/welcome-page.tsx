import cn from 'classnames';

import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import { Button } from '@app/shadcn/components/ui/button';
import { useFormState } from '@app/store/jotai/form';

import { useEffect, useState } from 'react';
import { useDebounceValue } from 'usehooks-ts';
import { FORM_COLUMN, columnPlacementClass, greetingAlignClass } from '../layout/form-column';
import GreetingLayoutWrapper from '../layout/greeting-layout-wrapper';

const WelcomeSlide = ({ disabled }: { disabled?: boolean }) => {
    const { theme, formState, setFormDescription, setFormTitle } = useFormState();
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
            {/* WYSIWYG with the respondent's welcome page: same column,
                alignment (the page's Layout setting) and rhythm. */}
            <div className="w-full">
                <div className={cn(FORM_COLUMN, columnPlacementClass(formState.welcomePage?.layout), 'flex flex-col pt-6', greetingAlignClass(formState.welcomePage?.layout))}>
                    <AutosizeTextarea
                        style={{ resize: 'none' }}
                        placeholder="Form Title"
                        aria-label="Form title"
                        // Textareas don't inherit text-align; [text-align:inherit] follows the column.
                        className="w-full border-0 bg-transparent px-0 py-0 text-[40px] font-bold leading-[48px] [text-align:inherit]"
                        value={formState.title}
                        onChange={(event) => {
                            setFormTitle(event.target.value);
                        }}
                    />
                    {formState?.welcomePage?.description !== undefined && formState?.welcomePage?.description !== null ? (
                        <>
                            <AutosizeTextarea
                                placeholder="Add description"
                                style={{ resize: 'none' }}
                                value={description}
                                aria-label="Description"
                                className="ring-none text-black-700 mt-4 w-full border-0 bg-transparent px-0 text-base leading-relaxed outline-hidden [text-align:inherit]"
                                onChange={(e: any) => setDescription(e.target.value)}
                            />
                        </>
                    ) : (
                        <></>
                    )}
                    <Button size={'medium'} className="z-10 mt-8 rounded px-8 py-3" style={{ background: theme?.secondary }}>
                        {formState.welcomePage?.buttonText || 'Start'}
                    </Button>
                </div>
            </div>
        </GreetingLayoutWrapper>
    );
};

export default WelcomeSlide;
