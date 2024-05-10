import BetterCollectedSmallLogo from '../Icons/BetterCollectedSmallLogo';

export default function FullScreenLoader() {
    return (
        <div
            data-testid="full-screen-loader"
            className="!z-[99990] flex min-h-[100vh] w-full items-center justify-center"
        >
            <BetterCollectedSmallLogo className="animate-pulse duration-300" />
        </div>
    );
}
