import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import { useFormState } from '@app/store/jotai/form';

import { IsValidString } from '@app/utils/string-utils';
import { FORM_COLUMN, columnPlacementClass, greetingAlignClass } from '../layout/form-column';
import GreetingLayoutWrapper from '../layout/greeting-layout-wrapper';

const ThankYouSlide = ({ disabled }: { disabled?: boolean }) => {
    const { formState, theme, setThankYouPageTitle, setThankYouPageDescription } = useFormState();
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();
    const layout = formState.thankyouPage?.[activeThankYouPageComponent?.index || 0]?.layout;
    return (
        <GreetingLayoutWrapper disabled={disabled} greetingIndex={-20} theme={theme}>
            {/* WYSIWYG with the respondent's ending page: same column,
                alignment (the page's Layout setting) and rhythm. */}
            <div className="w-full">
                <div className={cn(FORM_COLUMN, columnPlacementClass(layout), 'flex flex-col pt-6', greetingAlignClass(layout))}>
                    <AutosizeTextarea
                        style={{ resize: 'none' }}
                        placeholder="Thank You! 🎉"
                        aria-label="Ending title"
                        // Textareas don't inherit text-align; [text-align:inherit] follows the column.
                        className="w-full border-0 bg-transparent px-0 py-0 text-[40px] font-bold leading-[48px] [text-align:inherit]"
                        value={formState.thankyouPage![activeThankYouPageComponent?.index || 0]?.title ?? ''}
                        onChange={(event: any) => setThankYouPageTitle(activeThankYouPageComponent?.index || 0, event.target.value)}
                    />
                    {formState.thankyouPage && IsValidString(formState.thankyouPage[activeThankYouPageComponent?.index || 0].message) ? (
                        <AutosizeTextarea
                            placeholder="Your response has been successfully submitted"
                            value={formState.thankyouPage![activeThankYouPageComponent?.index || 0].message}
                            aria-label="Ending message"
                            className="ring-none text-black-700 mt-4 w-full border-0 bg-transparent px-0 text-base outline-hidden [text-align:inherit]"
                            onChange={(e: any) => setThankYouPageDescription(activeThankYouPageComponent?.index || 0, e.target.value)}
                        />
                    ) : (
                        <></>
                    )}
                    {formState.thankyouPage && IsValidString(formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonText) ? (
                        <Button size={'medium'} className="z-10 mt-8 rounded px-8 py-3" style={{ background: theme?.secondary }}>
                            {formState.thankyouPage![activeThankYouPageComponent?.index || 0].buttonText || 'Try bettercollected'}
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
