import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { useBuilderFormLogo } from '@app/lib/hooks/use-form-logo';
import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import { useFormState } from '@app/store/jotai/form';
import { IsValidString } from '@app/utils/string-utils';
import { LeafletTopRule } from '@app/views/molecules/form/leaflet-section';
import { leafletColours, styleTokens } from '@app/views/molecules/theme/theme-shared';

import { FORM_COLUMN, columnPlacementClass, greetingAlignClass } from '../layout/form-column';
import GreetingLayoutWrapper from '../layout/greeting-layout-wrapper';

const ThankYouSlide = ({ disabled }: { disabled?: boolean }) => {
    const { formState, theme, setThankYouPageTitle, setThankYouPageDescription } = useFormState();
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();
    const logo = useBuilderFormLogo();
    const layout = formState.thankyouPage?.[activeThankYouPageComponent?.index || 0]?.layout;
    if (styleTokens(theme?.style).key === 'leaflet') {
        // WYSIWYG with the respondent's leaflet ending: the title on the bar,
        // the message on the band; "What happens next" follows on the live
        // page (it is written from the form's privacy settings).
        const page = formState.thankyouPage?.[activeThankYouPageComponent?.index || 0];
        return (
            <GreetingLayoutWrapper disabled={disabled} greetingIndex={-20} theme={theme}>
                <div className="w-full">
                    {/* As on the live page: with a logo strip the top row goes. */}
                    {!logo && <LeafletTopRule theme={theme} />}
                    <div className="-mx-5 px-5 py-6 sm:-mx-8 sm:px-8 sm:py-8" style={{ background: theme?.secondary }}>
                        <div className={cn(FORM_COLUMN, columnPlacementClass(layout))}>
                            <AutosizeTextarea
                                style={{ resize: 'none', fontFamily: leafletSerif.style.fontFamily, fontWeight: 600 }}
                                placeholder="Thank you"
                                aria-label="Ending title"
                                className="w-full border-0 bg-transparent px-0 py-0 text-[30px] leading-[1.15] text-white placeholder:text-white/80 sm:text-[38px]"
                                value={page?.title ?? ''}
                                onChange={(event: any) => setThankYouPageTitle(activeThankYouPageComponent?.index || 0, event.target.value)}
                            />
                        </div>
                    </div>
                    <div className="-mx-5 px-5 py-4 sm:-mx-8 sm:px-8" style={{ background: leafletColours(theme).band }}>
                        <div className={cn(FORM_COLUMN, columnPlacementClass(layout))}>
                            <AutosizeTextarea
                                placeholder="Your answers have been sent."
                                value={page?.message ?? ''}
                                aria-label="Ending message"
                                style={{ resize: 'none', color: theme?.primary }}
                                className="ring-none w-full border-0 bg-transparent px-0 py-0 text-base leading-[1.6] outline-hidden"
                                onChange={(e: any) => setThankYouPageDescription(activeThankYouPageComponent?.index || 0, e.target.value)}
                            />
                        </div>
                    </div>
                    {IsValidString(page?.buttonText) && (
                        <div className={cn(FORM_COLUMN, columnPlacementClass(layout), 'pt-8')}>
                            <Button size={'medium'} className="z-10 min-h-12 rounded-[4px] px-8 py-3 text-base font-semibold" style={{ background: theme?.secondary }}>
                                {page?.buttonText}
                            </Button>
                        </div>
                    )}
                </div>
            </GreetingLayoutWrapper>
        );
    }

    return (
        <GreetingLayoutWrapper disabled={disabled} greetingIndex={-20} theme={theme}>
            {/* WYSIWYG with the respondent's ending page: same column,
                alignment (the page's Layout setting) and rhythm. */}
            <div className="w-full">
                <div className={cn(FORM_COLUMN, columnPlacementClass(layout), 'flex flex-col pt-6', greetingAlignClass(layout))}>
                    <AutosizeTextarea
                        style={{ resize: 'none' }}
                        placeholder="Thank you"
                        aria-label="Ending title"
                        // Textareas don't inherit text-align; [text-align:inherit] follows the column.
                        className="w-full border-0 bg-transparent px-0 py-0 [text-align:inherit] text-[40px] leading-[48px] font-bold"
                        value={formState.thankyouPage?.[activeThankYouPageComponent?.index || 0]?.title ?? ''}
                        onChange={(event: any) => setThankYouPageTitle(activeThankYouPageComponent?.index || 0, event.target.value)}
                    />
                    {formState.thankyouPage && IsValidString(formState.thankyouPage?.[activeThankYouPageComponent?.index || 0]?.message) ? (
                        <AutosizeTextarea
                            placeholder="Your answers have been sent."
                            value={formState.thankyouPage?.[activeThankYouPageComponent?.index || 0]?.message}
                            aria-label="Ending message"
                            className="ring-none mt-4 w-full border-0 bg-transparent px-0 [text-align:inherit] text-base text-black-700 outline-hidden"
                            onChange={(e: any) => setThankYouPageDescription(activeThankYouPageComponent?.index || 0, e.target.value)}
                        />
                    ) : (
                        <></>
                    )}
                    {formState.thankyouPage && IsValidString(formState.thankyouPage?.[activeThankYouPageComponent?.index || 0]?.buttonText) ? (
                        <Button size={'medium'} className="z-10 mt-8 rounded px-8 py-3" style={{ background: theme?.secondary }}>
                            {formState.thankyouPage?.[activeThankYouPageComponent?.index || 0]?.buttonText || 'Try bettercollected'}
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
