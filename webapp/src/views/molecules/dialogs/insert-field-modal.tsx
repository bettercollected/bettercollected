import { KeyboardEvent, useEffect, useId, useMemo, useState } from 'react';

import { Search } from 'lucide-react';

import { INSERT_CATEGORIES, InsertCatalogItem, bestInsertMatch, filterInsertCatalog } from '@app/constants/insert-field-catalog';
import { InsertPlacement, useInsertField } from '@app/lib/hooks/use-insert-field';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { InsertTarget } from '@app/store/jotai/insert-target';

/**
 * The Insert menu: search, then pick. Type to filter, ↑/↓ to move, Enter to
 * add to this page, Shift+Enter to add on a new page. Used by the navbar's
 * Insert button and by the canvas ("/", Ctrl/Cmd+K, "+" between questions),
 * where `target` fixes the position and only "add here" applies.
 */
const InsertFieldComponent = ({ formFields, activeSlideComponent, closeDropdown, target }: { formFields: StandardFormFieldDto[]; activeSlideComponent: { id: string; index: number } | null; closeDropdown: () => void; target?: InsertTarget | null }) => {
    const { insert } = useInsertField();
    const [query, setQuery] = useState('');
    const [activeIndex, setActiveIndex] = useState(0);
    const baseId = useId();
    const optionId = (index: number) => `${baseId}-option-${index}`;

    const results = useMemo(() => filterInsertCatalog(query), [query]);
    const active: InsertCatalogItem | undefined = results[Math.min(activeIndex, results.length - 1)];
    // A page to add to: the selected one, or the canvas target's.
    const hasPage = !!target || (!!activeSlideComponent && activeSlideComponent.index >= 0 && !!formFields?.[activeSlideComponent.index]);

    useEffect(() => {
        document.getElementById(optionId(activeIndex))?.scrollIntoView?.({ block: 'nearest' });
    }, [activeIndex]);

    const pick = (item: InsertCatalogItem | undefined, placement: InsertPlacement) => {
        if (!item) return;
        closeDropdown();
        insert(item, hasPage ? placement : 'new-page', target);
    };

    const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
        const last = results.length - 1;
        switch (event.key) {
            case 'ArrowDown':
                event.preventDefault();
                setActiveIndex((index) => (index >= last ? 0 : index + 1));
                break;
            case 'ArrowUp':
                event.preventDefault();
                setActiveIndex((index) => (index <= 0 ? last : index - 1));
                break;
            case 'Home':
            case 'PageUp':
                event.preventDefault();
                setActiveIndex(0);
                break;
            case 'End':
            case 'PageDown':
                event.preventDefault();
                setActiveIndex(Math.max(last, 0));
                break;
            case 'Enter':
                event.preventDefault();
                pick(active, event.shiftKey && !target ? 'new-page' : 'page');
                break;
            default:
                return;
        }
        // Keys the menu handled stay here (a surrounding menu or the
        // builder's shortcuts must not act on them too).
        event.stopPropagation();
    };

    return (
        <div id="fields-option" className="flex max-h-[min(560px,80vh)] w-[380px] flex-col bg-white">
            <div className="border-b border-black-300 p-3">
                <label htmlFor={`${baseId}-search`} className="sr-only">
                    Search field types
                </label>
                <div className="flex items-center gap-2 rounded border border-black-300 px-2.5 focus-within:border-brand-500">
                    <Search className="h-4 w-4 shrink-0 text-black-600" aria-hidden="true" />
                    <input
                        id={`${baseId}-search`}
                        // The menu opens to type in: focus belongs here.
                        // eslint-disable-next-line jsx-a11y/no-autofocus
                        autoFocus
                        type="text"
                        role="combobox"
                        aria-expanded="true"
                        aria-controls={`${baseId}-list`}
                        aria-autocomplete="list"
                        aria-activedescendant={active ? optionId(results.indexOf(active)) : undefined}
                        placeholder="Search field types"
                        autoComplete="off"
                        value={query}
                        onChange={(event) => {
                            setQuery(event.target.value);
                            setActiveIndex(bestInsertMatch(filterInsertCatalog(event.target.value), event.target.value));
                        }}
                        onKeyDown={onKeyDown}
                        className="w-full border-0 bg-transparent py-2 text-sm text-black-900 outline-hidden placeholder:text-black-600 focus:ring-0"
                    />
                </div>
            </div>
            <div id={`${baseId}-list`} role="listbox" aria-label="Field types" className="min-h-0 flex-1 overflow-y-auto py-1">
                {results.length === 0 && <p className="px-4 py-6 text-center text-sm text-black-600">No field type matches &ldquo;{query}&rdquo;</p>}
                {INSERT_CATEGORIES.map((category) => {
                    const items = results.filter((item) => item.category === category);
                    if (!items.length) return null;
                    const headingId = `${baseId}-${category.replace(/\W+/g, '-')}`;
                    return (
                        <div key={category} role="group" aria-labelledby={headingId}>
                            <div id={headingId} className="px-4 pt-3 pb-1 text-[11px] font-semibold tracking-wide text-black-600 uppercase">
                                {category}
                            </div>
                            {items.map((item) => {
                                const index = results.indexOf(item);
                                const selected = active === item;
                                return (
                                    <div
                                        key={item.type}
                                        id={optionId(index)}
                                        role="option"
                                        aria-selected={selected}
                                        aria-labelledby={`${optionId(index)}-name`}
                                        aria-describedby={`${optionId(index)}-desc`}
                                        data-umami-event="Insert Field Button"
                                        data-umami-event-field-type={item.type}
                                        // Options are picked with the pointer or from the search box (Enter).
                                        tabIndex={-1}
                                        onMouseMove={() => !selected && setActiveIndex(index)}
                                        onMouseDown={(event) => event.preventDefault()}
                                        onClick={() => pick(item, 'page')}
                                        onKeyDown={(event) => event.key === 'Enter' && pick(item, 'page')}
                                        className={cn('mx-1 flex cursor-pointer items-center gap-3 rounded px-3 py-2', selected ? 'bg-[#F4F7FD] text-black-900' : 'text-[#344054]')}
                                    >
                                        <span className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded border bg-white', selected ? 'border-brand-500' : 'border-black-300')}>{item.icon}</span>
                                        <span className="min-w-0">
                                            <span id={`${optionId(index)}-name`} className="block text-sm font-medium">{item.name}</span>
                                            <span id={`${optionId(index)}-desc`} className="block truncate text-xs text-black-600">
                                                {item.description}
                                            </span>
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    );
                })}
            </div>
            {/* The two ways to add, as separate actions on the highlighted type. */}
            <div className="flex items-center gap-2 border-t border-black-300 bg-black-100 p-3">
                <button type="button" disabled={!active} onClick={() => pick(active, 'page')} className="flex-1 rounded bg-brand-500 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-40">
                    {hasPage ? (target ? 'Add here' : 'Add to this page') : 'Add on a new page'}
                    <kbd aria-hidden="true" className="ml-2 font-sans text-xs opacity-80">
                        Enter
                    </kbd>
                </button>
                {hasPage && !target && (
                    <button type="button" disabled={!active} onClick={() => pick(active, 'new-page')} className="flex-1 rounded border border-black-400 bg-white px-3 py-2 text-sm font-medium text-black-800 hover:bg-black-200 disabled:opacity-40">
                        Add on a new page
                        <kbd aria-hidden="true" className="ml-2 font-sans text-xs text-black-600">
                            Shift+Enter
                        </kbd>
                    </button>
                )}
            </div>
        </div>
    );
};

export default InsertFieldComponent;
