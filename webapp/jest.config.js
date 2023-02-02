const nextJest = require('next/jest');
const createJestConfig = nextJest({
    dir: './'
});
const customJestConfig = {
    moduleNameMapper: {
        '^@app/(.*)$': '<rootDir>/src/$1'
    },
    moduleDirectories: ['node_modules', '<rootDir>/'],
    testEnvironment: 'jest-environment-jsdom',
    testMatch: ['**/__test__/*.ts?(x)']
};
module.exports = createJestConfig(customJestConfig);
