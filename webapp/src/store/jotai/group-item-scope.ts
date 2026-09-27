'use client';

import { createContext, useContext } from 'react';

import { ItemScope } from '@app/utils/repeating-groups';

/**
 * Set while one item of a repeating group renders. `useFormResponse` reads it
 * and presents that item's answers (layered over the form's) to the existing
 * field components, and writes their changes back into the item — so every
 * field type works inside a group without knowing about groups.
 */
export const GroupItemScopeContext = createContext<ItemScope | null>(null);

export const useGroupItemScope = () => useContext(GroupItemScopeContext);
