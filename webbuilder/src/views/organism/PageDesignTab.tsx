import { ThemeColors } from '@app/constants/theme';
import { Separator } from '@app/shadcn/components/ui/separator';
import { cn } from '@app/shadcn/util/lib';
import useFieldSelectorAtom from '@app/store/jotai/fieldSelector';

export default function PageDesignTab() {
    const { updateSlideTheme } = useFieldSelectorAtom();
    return (
        <div className='flex flex-col '>
            <span className="font-medium text-black-700 px-4 ">Theme</span>
            <Separator className='my-4' />
            <div className='flex flex-col gap-4 max-h-screen overflow-y-auto'>
                {ThemeColors.map((themeColor) => {
                    return <div className='cursor-pointer' onClick={() => updateSlideTheme(themeColor)}>
                        <ThemeComponent color={themeColor} />
                        <Separator className='my-3' />
                    </div>
                })}
            </div>
        </div>
    );
}

const ThemeComponent = ({ color }: { color: any }) => {
    const { name, primary, secondary, tertiary, accent } = color
    return <div className='flex flex-col items-start gap-2 m-2'>
        <div style={{
            background: accent
        }} className="rounded-lg w-full h-[100px] flex flex-col gap-1 border border-black-300 px-6 py-3">
            <h1 style={{ color: primary }}>Question</h1>
            <h1 style={{ color: tertiary }}>Answer Field</h1>
            <div style={{ background: secondary }} className='w-[35px] h-[13px] rounded-sm' />
        </div>
        <div className="flex gap-2 px-3">
            <ThemeColorBox
                color={accent}
            />
            <ThemeColorBox
                color={tertiary}
            />
            <ThemeColorBox
                color={secondary}
            />
            <ThemeColorBox
                color={primary}
            />
        </div>
        <h1 className='text-xs font-normal'>{name}</h1>
    </div>
}

const ThemeColorBox = ({ color }: { color: string }) => {
    return (
        <div
            className={cn('h-6 w-6 rounded border')}
            style={{ background: color }}
        ></div>
    );
};
