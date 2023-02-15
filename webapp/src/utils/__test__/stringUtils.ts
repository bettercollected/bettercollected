import { capitalize, toEndDottedStr, toMidDottedStr } from '@app/utils/stringUtils';

describe('test capitalizing first letter', () => {
    it('should capitalize if string is provided', function () {
        const capitalized = capitalize('hello');
        expect(capitalized).toStrictEqual('Hello');
    });
    it('should capitalize if string is provided', function () {
        const capitalized = capitalize('');
        expect(capitalized).toStrictEqual('');
    });
});

describe('return end dotted string form string', () => {
    it('should return end dotted string if length of string is greater than leading visible', function () {
        const str = 'should return end dotted string if length of string is greater than leading visible';
        const dottedString1 = toEndDottedStr(str, 5);
        expect(dottedString1).toStrictEqual('shoul...');
        const dottedString2 = toEndDottedStr('str', 5);
        expect(dottedString2).toStrictEqual('str');
    });
});

describe('return mid dotted string form string', () => {
    it('should return end dotted string if length of string is greater than leading visible', function () {
        const str = 'should return end dotted string if length of string is greater than leading visible';
        const dottedString1 = toMidDottedStr(str, 5);
        expect(dottedString1).toStrictEqual('shoul...sible');
        const dottedString2 = toMidDottedStr('str', 5);
        expect(dottedString2).toStrictEqual('str');
    });
});
