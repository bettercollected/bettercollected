import SlideCanvas from '@app/views/molecules/SlideCanvas';

export default function Home() {
    return (
        // DO NOT REMOVE OR ADD ANY PADDING OR MARGIN HERE, PADDING IS USED TO SUBTRACT IN THE NEARBY ELEMENT DETECTION ON CANVAS
        <main className="flex min-h-screen flex-col items-center justify-start bg-black-100">
            <div id="navbar" className="h-16 w-full bg-white shadow-lg">
                adf
            </div>
            <div className="flex flex-row w-full h-full">
                <div id="slides-preview" className="w-[400px] self-stretch  m-5 bg-white">
                    Slides Preview
                </div>
                <SlideCanvas/>
                <div className="w-[400px] m-5 bg-white self-stretch">
                    Element Properties
                </div>
            </div>
        </main>
    );
}
