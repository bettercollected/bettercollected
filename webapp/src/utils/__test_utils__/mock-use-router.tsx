export default function mockUseRouter(query: any, path: any) {
    jest.mock('next/router', () => ({
        useRouter() {
            return {
                route: '/',
                pathname: path,
                query: query,
                asPath: '',
                push: jest.fn(),
                events: {
                    on: jest.fn(),
                    off: jest.fn()
                },
                beforePopState: jest.fn(() => null),
                prefetch: jest.fn(() => null)
            };
        }
    }));
}
