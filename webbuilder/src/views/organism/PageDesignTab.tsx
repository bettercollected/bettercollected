import { ButtonVariant } from '@app/models/enums/button';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import useFieldSelectorAtom from '@app/store/jotai/fieldSelector';

export default function PageDesignTab() {
    const { activeSlide } = useFieldSelectorAtom();
    return (
        <>
            <div className="mb-4 mt-6 flex items-center justify-between px-4">
                <span className="p2-new text-black-700">Theme</span>
                <Button
                    className="rounded-lg !px-2 "
                    size={'xs'}
                    variant={ButtonVariant.Tertiary}
                >
                    Customize
                </Button>
            </div>
            <div className="flex gap-2 px-4">
                <ThemeColorBox
                    color={activeSlide?.properties?.theme?.accent || '#F5FFFE'}
                />
                <ThemeColorBox
                    color={activeSlide?.properties?.theme?.tertiary || '#B1E0DE'}
                />
                <ThemeColorBox
                    color={activeSlide?.properties?.theme?.secondary || '#407270'}
                />
                <ThemeColorBox
                    color={activeSlide?.properties?.theme?.primary || '#2E2E2E'}
                />
            </div>
        </>
    );
}

const ThemeColorBox = ({ color }: { color: string }) => {
    return (
        <div
            className={cn('h-6 w-6 rounded border')}
            style={{ background: color }}
        ></div>
    );
};
