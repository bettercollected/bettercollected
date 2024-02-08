import SlideCanvas from '@app/views/molecules/SlideCanvas';

export default function Home() {
    return (
        <main className="flex min-h-screen flex-col items-center justify-between bg-black-100 p-4">
            <SlideCanvas />
        </main>
    );
}
