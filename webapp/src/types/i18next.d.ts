import 'i18next';

// i18next 27 types differ from 26 in two defaults; keep the 26 ones, as the runtime options do
// (src/shared/hocs/i18n-provider.tsx sets returnEmptyString: true):
// - strictInterpolationChecks: with true (the 27 default) a `t` typed with a plain `string` key is no longer
//   assignable to the `(key: string, options?: Record<string, unknown>) => string` helper types the app passes it to;
// - returnEmptyString: an empty translation is a translation.
declare module 'i18next' {
    interface CustomTypeOptions {
        strictInterpolationChecks: false;
        returnEmptyString: true;
    }
}
