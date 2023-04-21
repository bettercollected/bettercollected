import { parseDate, parseDateStrToDate } from '@app/utils/dateUtils';

describe('Date utils', () => {
    it('should parse date milliseconds from string', function () {
        const date = new Date();
        const parsedDate = parseDate(date.toLocaleString());
        // expect(Math.round(date.valueOf() / 1000)).toBe(Math.round(parsedDate / 1000));
    });

    it('should parse date form date string', function () {
        const date = new Date();
        const parsedDate = parseDateStrToDate(date.toLocaleString());
        expect(parsedDate).toStrictEqual(new Date(date.setMilliseconds(0)));
    });
});
