import { ThemeColors } from '@app/constants/theme';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { Separator } from '@app/shadcn/components/ui/separator';
import { cn } from '@app/shadcn/util/lib';
import { useAuthAtom } from '@app/store/jotai/auth';
import { useFormState } from '@app/store/jotai/form';

export default function PageDesignTab() {
    const { updateFormTheme, theme } = useFormState();
    const { authState } = useAuthAtom();
    return (
        <div className="flex h-full flex-col ">
            <span className="text-black-700 px-4 font-medium ">Theme</span>
            <Separator className="mt-4" />
            <ScrollArea className="max-h-design-content flex flex-col overflow-y-auto p-2">
                {ThemeColors.map((themeColor, index) => {
                    return (
                        <button key={index} data-umami-event={'Update New Theme Button'} data-umami-event-email={authState.email}>
                            <div
                                className={`hover:bg-black-200 mb-2 cursor-pointer rounded-lg border-[1px] ${theme?.title === themeColor.title && 'border-brand-500'}`}
                                onClick={() => {
                                    updateFormTheme(themeColor);
                                }}
                            >
                                <ThemeComponent color={themeColor} />
                            </div>
                        </button>
                    );
                })}
            </ScrollArea>
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
                className="border-black-300 flex h-[100px] w-full flex-col gap-1 rounded-lg border px-6 py-3"
            >
                <h1 style={{ color: primary }}>Question</h1>
                <h1 style={{ color: tertiary }}>Answer Field</h1>
                <div style={{ background: secondary }} className="h-[13px] w-[35px] rounded-sm" />
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
    return <div className={cn('h-6 w-6 rounded border')} style={{ background: color }}></div>;
};
