import { FormSlideLayout } from '@app/models/enums/form';
import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useActiveThankYouPageComponent } from '@app/store/jotai/activeBuilderComponent';
import { useFormState } from '@app/store/jotai/form';

import GreetingLayoutWrapper from '../Layout/GreetingLayoutWrapper';

const ThankYouSlide = ({ disabled }: { disabled?: boolean }) => {
    const { formState, theme, setThankYouPageDescription } = useFormState();
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();
    return (
        <GreetingLayoutWrapper disabled={disabled} greetingIndex={-20} theme={theme}>
            <div
                className={cn(
                    'flex w-full  items-start',
                    formState.thankyouPage![activeThankYouPageComponent?.index || 0]
                        ?.layout ===
                        FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN
                        ? 'justify-start'
                        : ' justify-center'
                )}
            >
                <div className="flex w-full max-w-[800px] flex-col items-start">
                    <h1 className="text-[40px] font-semibold">Thank You! 🎉</h1>
                    {formState.thankyouPage &&
                    formState.thankyouPage[activeThankYouPageComponent?.index || 0]
                        .message !== undefined ? (
                        <AutosizeTextarea
                            placeholder="Your response has been successfully submitted"
                            value={
                                formState.thankyouPage![
                                    activeThankYouPageComponent?.index || 0
                                ].message
                            }
                            className="ring-none w-full border-0 px-0 text-base text-black-600 outline-none"
                            onChange={(e: any) =>
                                setThankYouPageDescription(
                                    activeThankYouPageComponent?.index || 0,
                                    e.target.value
                                )
                            }
                        />
                    ) : (
                        <></>
                    )}
                    {formState.thankyouPage &&
                    formState.thankyouPage[activeThankYouPageComponent?.index || 0]
                        .buttonText !== undefined ? (
                        <Button
                            size={'medium'}
                            className="z-10 mt-12 rounded px-8 py-3"
                            style={{ background: theme?.secondary }}
                        >
                            {formState.thankyouPage![
                                activeThankYouPageComponent?.index || 0
                            ].buttonText || 'Try bettercollected'}
                        </Button>
                    ) : (
                        <></>
                    )}
                </div>
            </div>
        </GreetingLayoutWrapper>
    );
};

export default ThankYouSlide;
