import FieldSettings from "@app/views/organism/FieldSettings";

export default function PropertiesDrawer() {

    const shouldShowSettings = true

    return <div className="flex flex-col divider-black-100 border-b-black-100 border-b">
        {
            shouldShowSettings && <FieldSettings/>
        }
    </div>
}