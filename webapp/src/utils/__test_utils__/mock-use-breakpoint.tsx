export default function mockUseBreakPoint(breakpoint: string) {
    jest.mock('@app/lib/hooks/use-breakpoint', () => ({
        useBreakpoint: () => breakpoint
    }));
}
