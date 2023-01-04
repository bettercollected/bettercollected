import { useState } from 'react';

export default function Dropdown() {
    const [showDropdown, setShowDropdown] = useState(false);
    return (
        <div className="mb-4">
            <h3 className="text-lg mb-2 font-medium">Dropdown</h3>
            <button
                id="dropdownDefault"
                onClick={() => setShowDropdown(!showDropdown)}
                data-dropdown-toggle="dropdown"
                className="text-gray-600 border-[1px] border-[#eaeaea] font-medium rounded-md text-sm px-4 py-2.5 text-center inline-flex items-center"
                type="button"
            >
                Dashboard{' '}
                <svg className="ml-2 w-4 h-4" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path>
                </svg>
            </button>
            <div id="dropdown" className={`${showDropdown ? '' : 'hidden'} z-10 w-44 bg-white rounded divide-y divide-gray-100 shadow dark:bg-gray-700`}>
                <ul className="py-1 text-sm text-gray-700 dark:text-gray-200" aria-labelledby="dropdownDefault">
                    <li>
                        <p className="block py-2 px-4 hover:bg-gray-100 dark:hover:bg-gray-600 dark:hover:text-white">Dashboard</p>
                    </li>
                    <li>
                        <p className="block py-2 px-4 hover:bg-gray-100 dark:hover:bg-gray-600 dark:hover:text-white">Settings</p>
                    </li>
                </ul>
            </div>
        </div>
    );
}
