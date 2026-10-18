import cn from 'classnames';

import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { useBuilderFormLogo } from '@app/lib/hooks/use-form-logo';
import { AutosizeTextarea } from '@app/shadcn/components/ui/autosize-textarea';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { LeafletContents, LeafletTopRule } from '@app/views/molecules/form/leaflet-section';
import { canvasButtonStyle } from '@app/views/molecules/theme/theme-root';
import { leafletColours, styleTokens } from '@app/views/molecules/theme/theme-shared';

import { FORM_COLUMN, columnPlacementClass, greetingAlignClass } from '../layout/form-column';
import GreetingLayoutWrapper from '../layout/greeting-layout-wrapper';

const WelcomeSlide = ({ disabled }: { disabled?: boolean }) => {
    const { theme, formState, setFormDescription, setFormTitle } = useFormState();
    const logo = useBuilderFormLogo();
    // The pages, for the leaflet cover's contents.
    const form = useAppSelector(selectForm);
    // Read from and written to the form state directly: showing the page
    // writes nothing, and typing is one undo step (the setter coalesces).
    const description = formState?.welcomePage?.description ?? '';
    const setDescription = (value: string) => setFormDescription(value);

    if (styleTokens(theme?.style).key === 'leaflet') {
        // WYSIWYG with the respondent's leaflet cover: the title edited on the
        // section bar, the description on the intro band.
        const layout = formState.welcomePage?.layout;
        return (
            <GreetingLayoutWrapper theme={theme} disabled={disabled} greetingIndex={-10}>
                <div className="w-full">
                    {/* As on the live page: with a logo strip the top row goes. */}
                    {!logo && <LeafletTopRule theme={theme} />}
                    <div className="-mx-5 px-5 py-6 sm:-mx-8 sm:px-8 sm:py-8" style={{ background: theme?.secondary }}>
                        <div className={cn(FORM_COLUMN, columnPlacementClass(layout))}>
                            <AutosizeTextarea
                                style={{ resize: 'none', fontFamily: leafletSerif.style.fontFamily, fontWeight: 600 }}
                                placeholder="Form Title"
                                aria-label="Form title"
                                className="w-full border-0 bg-transparent px-0 py-0 text-[30px] leading-[1.15] text-white placeholder:text-white/80 sm:text-[38px]"
                                value={formState.title}
                                onChange={(event) => {
                                    setFormTitle(event.target.value);
                                }}
                            />
                        </div>
                    </div>
                    {formState?.welcomePage?.description !== undefined && formState?.welcomePage?.description !== null && (
                        <div className="-mx-5 px-5 py-4 sm:-mx-8 sm:px-8" style={{ background: leafletColours(theme).band }}>
                            <div className={cn(FORM_COLUMN, columnPlacementClass(layout))}>
                                <AutosizeTextarea
                                    placeholder="Add description"
                                    style={{ resize: 'none', color: theme?.primary }}
                                    value={description}
                                    aria-label="Description"
                                    className="ring-none w-full border-0 bg-transparent px-0 py-0 text-base leading-[1.6] outline-hidden"
                                    onChange={(e: any) => setDescription(e.target.value)}
                                />
                            </div>
                        </div>
                    )}
                    <div className={cn(FORM_COLUMN, columnPlacementClass(layout), 'flex flex-col items-start pt-8')}>
                        <LeafletContents pages={form?.fields} theme={theme} />
                        <Button size={'medium'} className="z-10 mt-8 min-h-12 rounded-[4px] px-8 py-3 text-base font-semibold" style={canvasButtonStyle(theme, '4px')}>
                            {formState.welcomePage?.buttonText || 'Start'}
                        </Button>
                    </div>
                </div>
            </GreetingLayoutWrapper>
        );
    }

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
                        // The theme's title face and width, as on the live page (theme-root.ts).
                        className="form-title-face form-display-title w-full border-0 bg-transparent px-0 py-0 [text-align:inherit] text-[40px] leading-[48px] font-bold"
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
                                className="ring-none mt-4 w-full border-0 bg-transparent px-0 [text-align:inherit] text-base leading-relaxed text-black-700 outline-hidden"
                                onChange={(e: any) => setDescription(e.target.value)}
                            />
                        </>
                    ) : (
                        <></>
                    )}
                    <Button size={'medium'} className="z-10 mt-8 rounded px-8 py-3" style={canvasButtonStyle(theme, '8px')}>
                        {formState.welcomePage?.buttonText || 'Start'}
                    </Button>
                </div>
            </div>
        </GreetingLayoutWrapper>
    );
};

export default WelcomeSlide;
