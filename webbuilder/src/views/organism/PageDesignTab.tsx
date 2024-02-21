import {Button} from "@app/shadcn/components/ui/button";
import {ButtonVariant} from "@app/models/enums/button";
import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";
import {cn} from "@app/shadcn/util/lib";

export default function PageDesignTab() {
    const {activeSlide} = useFieldSelectorAtom()
    return <>
        <div className="px-4 mt-6 mb-4 flex items-center justify-between">
            <span className="p2-new text-black-700">
            Theme
            </span>
            <Button className="rounded-lg !px-2 " size={"xs"} variant={ButtonVariant.Tertiary}>
                Customize
            </Button>
        </div>
        <div className="flex gap-2 px-4">
            <ThemeColorBox color={activeSlide?.properties?.theme?.accent || "#F5FFFE"}/>
            <ThemeColorBox color={activeSlide?.properties?.theme?.tertiary || "#B1E0DE"}/>
            <ThemeColorBox color={activeSlide?.properties?.theme?.secondary || "#407270"}/>
            <ThemeColorBox color={activeSlide?.properties?.theme?.primary || "#2E2E2E"}/>
        </div>
    </>
}

const ThemeColorBox = ({color}: { color: string }) => {
    return <div className={cn("w-6 h-6 rounded border")} style={{background: color}}>
    </div>
}