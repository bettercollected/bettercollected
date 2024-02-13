import SlideCanvas from '@app/views/molecules/SlideCanvas';

export default function Home() {
    return (
        <main className="flex min-h-screen flex-col items-center justify-start bg-black-100">
            <div id="navbar" className="h-16 w-full bg-white shadow-lg">
                adf
            </div>
            <div className="flex h-full w-full flex-row">
                <div
                    id="slides-preview"
                    className="m-5 w-[400px]  self-stretch bg-white"
                >
                    Slides Preview
                </div>
                <SlideCanvas />
                <div
                    id="slide-element-properties"
                    className="m-5 w-[400px] self-stretch bg-white"
                >
                    Element Properties
                </div>
            </div>
        </main>
    );
}
