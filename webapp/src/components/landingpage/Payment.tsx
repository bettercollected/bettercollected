import HeadingRenderer from "@app/components/ui/HeadingRenderer";

export default function Payment(){
    return(
        <div className="py-8 px-4 mx-auto max-w-screen-xl lg:py-16 lg:px-6">
            {/* --------Header--------- */}
            <HeadingRenderer description={"Here at Flowbite we focus on markets where technology, innovation, and capital can unlock long-term value and drive economic growth."}>
                Ready to get started?
            </HeadingRenderer>
            {/* ---------Card container---------- */}
            <div className="space-y-8 lg:grid lg:grid-cols-3 sm:gap-6 xl:gap-10 lg:space-y-0">
                {/* ------------------card 1----------------------- */}
                <div className="flex flex-col p-6 mx-auto max-w-lg text-start text-dark bg-white rounded-3xl shadow-lg">
                    <div className="flex justify-start item-baseline ">
                        {/* place for icons */}
                        <span className="text-2xl font-semibold">Starter</span>
                    </div>
                    <p className="font-light text-gray-500 sm:text-md ">Best option for personal use & for your next
                        project.</p>
                    {/* ----------Pricing----------- */}
                    <div className="flex justify-center items-baseline my-8">
                        <span className="mr-2 text-6xl font-bold">$9</span>
                        <span className="text-gray-500 ">/month</span>
                    </div>
                    {/* ------------Get started button ------------- */}
                    <a href="#"
                       className="text-white bg-dark hover:bg-primary focus:ring-4 focus:ring-primary-200 font-medium rounded-lg text-sm px-5 py-2.5 text-center">Try
                        7 days for free</a>
                    {/* -----------Features---------- */}
                    <ul role="list" className="mt-3 mb-8 space-y-4 text-left">
                        <li className="flex items-center space-x-3">
                            <h3 className=' text-lg font-bold'>Features</h3>
                            <p></p>
                        </li>
                        <li className="flex items-center space-x-3">
                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                                 fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Individual configuration</span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                                 fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>No setup, or hidden fees</span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                                 fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Team size: <span className="font-semibold">1 developer</span></span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                                 fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Premium support: <span className="font-semibold">6 months</span></span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                                 fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Free updates: <span className="font-semibold">6 months</span></span>
                        </li>
                    </ul>
                </div>


                {/* ------------------card 2----------------------- */}
                <div className="flex flex-col p-6 mx-auto max-w-lg text-start text-white bg-dark rounded-3xl shadow-lg">
                    <div className="flex justify-start item-baseline ">
                        {/* place for icons */}
                        <span className="text-2xl font-semibold text-primary">Pro</span>
                    </div>
                    <p className="font-light text-gray-500 sm:text-md ">Best option for personal use & for your next
                        project.</p>
                    {/* ----------Pricing----------- */}
                    <div className="flex justify-center items-baseline my-8">
                        <span className="mr-2 text-6xl font-bold">$29</span>
                        <span className="text-gray-500 ">/month</span>
                    </div>
                    <a href="#"
                       className="text-white bg-primary hover:bg-white hover:text-primary focus:ring-4 focus:ring-primary-200 font-medium rounded-lg text-sm px-5 py-2.5 text-center">Get
                        Started</a>
                    {/* -----------Features---------- */}
                    <ul role="list" className="mt-3 mb-8 space-y-4 text-left">
                        <li className="flex items-center space-x-3">
                            <h3 className=' text-lg font-bold'>Features</h3>
                            <p></p>
                        </li>
                        <li className="flex items-center space-x-3">
                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                                 fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Individual configuration</span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                                 fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>No setup, or hidden fees</span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                                 fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Team size: <span className="font-semibold">1 developer</span></span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                                 fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Premium support: <span className="font-semibold">6 months</span></span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 dark:text-green-400"
                                 fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Free updates: <span className="font-semibold">6 months</span></span>
                        </li>
                    </ul>

                </div>
                {/* ------------------card 3----------------------- */}
                <div className="flex flex-col p-6 mx-auto max-w-lg text-start text-dark bg-white rounded-3xl shadow-lg">
                    <div className="flex justify-start item-baseline ">
                        {/* place for icons */}
                        <span className="text-2xl font-semibold">Ultra Pro Max</span>
                    </div>
                    <p className="font-light text-gray-500 sm:text-md ">Best option for personal use & for your next
                        project.</p>
                    {/* ----------Pricing----------- */}
                    <div className="flex justify-center items-baseline my-8">
                        <span className="mr-2 text-6xl font-bold">$99</span>
                        <span className="text-gray-500 ">/month</span>
                    </div>
                    {/* -------------Get started button--------------  */}
                    <a href="#"
                       className="text-white bg-dark hover:bg-primary focus:ring-4 focus:ring-primary-200 font-medium rounded-lg text-sm px-5 py-2.5 text-center">Get
                        Started</a>
                    {/* -----------Features---------- */}
                    <ul role="list" className="mt-3 mb-8 space-y-4 text-left">
                        <li className="flex items-center space-x-3">
                            <h3 className=' text-lg font-bold'>Features</h3>
                            <p></p>
                        </li>
                        <li className="flex items-center space-x-3">
                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 " fill="currentColor"
                                 viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Individual configuration</span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 " fill="currentColor"
                                 viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>No setup, or hidden fees</span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 " fill="currentColor"
                                 viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Team size: <span className="font-semibold">1 developer</span></span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 " fill="currentColor"
                                 viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Premium support: <span className="font-semibold">6 months</span></span>
                        </li>
                        <li className="flex items-center space-x-3">

                            <svg className="flex-shrink-0 w-5 h-5 text-green-500 " fill="currentColor"
                                 viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd"
                                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                      clipRule="evenodd"></path>
                            </svg>
                            <span>Free updates: <span className="font-semibold">6 months</span></span>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    );
}