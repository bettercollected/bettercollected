import SlideCanvas from '@app/views/molecules/SlideCanvas';

export default function Home() {
    return (
        // DO NOT REMOVE OR ADD ANY PADDING OR MARGIN HERE, PADDING IS USED TO SUBTRACT IN THE NEARBY ELEMENT DETECTION ON CANVAS
        <main className="flex min-h-screen flex-col items-center justify-between bg-black-100 p-4">
            <SlideCanvas />
        </main>
    );
}
