import { ThemeColors } from '@app/constants/theme';
import { Separator } from '@app/shadcn/components/ui/separator';
import { cn } from '@app/shadcn/util/lib';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFieldSelectorAtom from '@app/store/jotai/fieldSelector';

export default function PageDesignTab() {
    const { updateSlideTheme, activeSlide } = useFieldSelectorAtom();
    return (
        <div className="flex h-full flex-col ">
            <span className="px-4 font-medium text-black-700 ">Theme</span>
            <Separator className="mt-4" />
            <div className="flex max-h-design-content flex-col overflow-y-auto">
                {ThemeColors.map((themeColor) => {
                    return (
                        <div
                            className={`cursor-pointer border-[1px] hover:bg-black-200 ${activeSlide?.properties?.theme?.title === themeColor.title && 'border-brand-500'}`}
                            onClick={() => {
                                updateSlideTheme(themeColor);
                            }}
                        >
                            <ThemeComponent color={themeColor} />
                            {/* <Separator /> */}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

const ThemeComponent = ({ color }: { color: any }) => {
    const { title, primary, secondary, tertiary, accent } = color;
    return (
        <div className="flex flex-col items-start gap-2 px-2 py-4">
            <div
                style={{
                    background: accent
                }}
                className="flex h-[100px] w-full flex-col gap-1 rounded-lg border border-black-300 px-6 py-3"
            >
                <h1 style={{ color: primary }}>Question</h1>
                <h1 style={{ color: tertiary }}>Answer Field</h1>
                <div
                    style={{ background: secondary }}
                    className="h-[13px] w-[35px] rounded-sm"
                />
            </div>
            <div className="flex gap-2 px-3">
                <ThemeColorBox color={accent} />
                <ThemeColorBox color={tertiary} />
                <ThemeColorBox color={secondary} />
                <ThemeColorBox color={primary} />
            </div>
            <h1 className="text-xs font-normal">{title}</h1>
        </div>
    );
};

const ThemeColorBox = ({ color }: { color: string }) => {
    return (
        <div
            className={cn('h-6 w-6 rounded border')}
            style={{ background: color }}
        ></div>
    );
};
