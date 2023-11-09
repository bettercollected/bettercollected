import { builder } from './builderSlice';

export const {
    addCondition,
    addDuplicateField,
    deleteCondition,
    setActiveChoice,
    setActiveField,
    setAddNewChoice,
    setBuilderMenuState,
    resetBuilderMenuState,
    setBuilderState,
    setCommandMenuPosition,
    setDeleteChoice,
    setDeleteField,
    setEditForm,
    setFields,
    setIdentifierField,
    setMoveField,
    resetForm,
    setAddNewField,
    setTyping,
    setUpdateCommandField,
    setUpdateField,
    updateAction,
    updateConditional,
    updateConditionalOperator
} = builder.actions;
