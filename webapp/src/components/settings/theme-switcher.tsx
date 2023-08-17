/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-14
 * Time: 12:39
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { useTheme } from 'next-themes';

import { RadioGroup } from '@headlessui/react';

import { Moon } from '@app/components/icons/moon';
import { Sun } from '@app/components/icons/sun';

export default function ThemeSwitcher() {
    const { theme, setTheme } = useTheme();

    return (
        <div className="px-6 pt-8">
            <RadioGroup value={theme} onChange={setTheme} className="grid grid-cols-2 gap-5 ">
                <RadioGroup.Option value="light">
                    {({ checked }) => (
                        <div className="group cursor-pointer">
                            <span
                                className={`flex h-[70px] items-center justify-center rounded-lg text-center text-sm font-medium uppercase tracking-wide transition-all ${
                                    checked ? 'bg-white shadow-large dark:bg-gray-600' : 'bg-gray-100 text-gray-500 group-hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:group-hover:bg-gray-700'
                                }`}
                            >
                                <Sun />
                            </span>
                            <span className={`mt-3 block text-center text-sm transition-all ${checked ? 'text-brand dark:text-white' : 'text-gray-500 group-hover:text-gray-900 dark:text-gray-400 dark:group-hover:text-white'}`}>Light</span>
                        </div>
                    )}
                </RadioGroup.Option>
                <RadioGroup.Option value="dark">
                    {({ checked }) => (
                        <div className="group cursor-pointer">
                            <span
                                className={`flex h-[70px] items-center justify-center rounded-lg text-center text-sm font-medium uppercase tracking-wide transition-all ${
                                    checked ? 'bg-white shadow-large dark:bg-gray-600' : 'bg-gray-100 text-gray-500 group-hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:group-hover:bg-gray-700'
                                }`}
                            >
                                <Moon />
                            </span>
                            <span className={`mt-3 block text-center text-sm transition-all ${checked ? 'text-brand dark:text-white' : 'text-gray-500 group-hover:text-gray-900 dark:text-gray-400 dark:group-hover:text-white'}`}>Dark</span>
                        </div>
                    )}
                </RadioGroup.Option>
            </RadioGroup>
        </div>
    );
}
