import SlideCanvas from '@app/views/molecules/SlideCanvas';
import Navbar from '@app/views/organism/Navbar';
import PropertiesDrawer from "@app/views/organism/PropertiesDrawer";

export default function Home() {
    return (
        <main className="flex min-h-screen flex-col items-center justify-start bg-black-100">
            <Navbar/>
            <div className="flex h-body-content gap-10  w-full flex-row items-center">
                <div
                    id="slides-preview"
                    className="w-[400px] h-full bg-white"
                >
                    Slides Preview
                </div>
                <div className=" h-min w-full aspect-video bg-white">

                </div>
                {/*<SlideCanvas/>*/}
                <div
                    id="slide-element-properties"
                    className="w-[400px] self-stretch bg-white"
                >
                    <PropertiesDrawer/>
                </div>
            </div>
        </main>
    );
}
