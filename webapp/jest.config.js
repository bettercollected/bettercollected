const nextJest = require('next/jest');
const createJestConfig = nextJest({
    dir: './'
});
const customJestConfig = {
    moduleNameMapper: {
        '^@app/(.*)$': '<rootDir>/src/$1'
    },
    setupFilesAfterEnv: ['<rootDir>/src/utils/__test_utils__/setupTests.ts', 'jest-canvas-mock'],
    moduleDirectories: ['node_modules', '<rootDir>/'],
    testEnvironment: 'jest-environment-jsdom',
    testMatch: ['**/__test__/*.ts?(x)'],
    transform: {
        '^.+\\.(ts|tsx)?$': 'ts-jest'
    }
};

async function jestConfig() {
    const nextJestConfig = await createJestConfig(customJestConfig)();
    nextJestConfig.transformIgnorePatterns = ['/node_modules/(?!uuid)/'];
    return nextJestConfig;
}

module.exports = jestConfig();
