"""When a response that offered an answer as an option is erased.

Another form's answers become options (``shareAsChoices``), and a respondent of
a consuming form who chose one has the text stored next to the option id (the
label snapshot). When the person whose answer it was is erased, that text must
not outlive them in other people's responses: once no eligible response still
offers the option, every snapshot of it is replaced by ``REMOVED_LABEL``.

How it is made reliable, whichever way the erasure happens (a completed
deletion request, a staff delete, retention, account or form deletion: every
delete of a response goes through ``PostgresFormResponseRepository``):

1. In the transaction that deletes responses, the repository notes which
   options the erased responses offered (``option_ids``, keyed hashes, never
   the text) in ``option_source_erasures``: erasure and note commit or roll
   back together.
2. ``OptionSourceService.redact_erased`` (right after the erasure, and every
   few minutes in the jobs worker) works through the notes: an option that is
   no longer offered is redacted in every consuming response of the workspace,
   then the note is removed. It is idempotent (a redacted snapshot is not
   touched again) and a failed run leaves the note for the next one.

What cannot be undone: webhooks and emails sent before the redaction, exports
already downloaded and a respondent's own saved draft keep what they held.
"""

from typing import Any, Dict, Iterable, List, Mapping, Optional, Set

from backend.app.services.option_sources import ids, read, text

REMOVED_LABEL = "[removed]"


def answer_labels(raw: Any, kind: Optional[str], choice_labels: Mapping[str, str]):
    """The cleaned labels one answer to a source question gives (a text
    answer's text, or the labels of the chosen options)."""
    if not isinstance(raw, dict):
        return []
    if kind == "short_text":
        candidates: List[Any] = [raw.get("text")]
    else:
        chosen: List[Any] = []
        single = raw.get("choice")
        multiple = raw.get("choices")
        if isinstance(single, dict):
            chosen.append(single.get("value"))
        if isinstance(multiple, dict):
            values = multiple.get("values")
            chosen.extend(values if isinstance(values, list) else [])
        candidates = [choice_labels.get(c) for c in chosen if isinstance(c, str)]
    found = []
    for candidate in candidates:
        label = text.clean(candidate, text.LABEL_MAX)
        if label is not None:
            found.append(label)
    return found


def offered_option_ids(
    workspace_id: Any,
    form_id: Any,
    form: Any,
    answers: Mapping[str, Any],
    shared: Iterable[str],
) -> Dict[str, List[str]]:
    """``{question id: option ids}`` that a response with these decrypted
    answers offered to other forms: its answers to the questions it shared
    (``form`` is the version it was filled on). May raise ``ids.NoIdKey``."""
    questions = {
        str(read.get(q, "id")): q for q in read.page_questions(form)
    }
    found: Dict[str, List[str]] = {}
    for question_id in shared:
        question = questions.get(str(question_id))
        if question is None:
            continue
        kind = read.field_type(question)
        choice_labels = read.static_labels(question) if kind != "short_text" else {}
        option_ids = {
            ids.answer_option_id(workspace_id, form_id, question_id, text.fold(label))
            for label in answer_labels(
                answers.get(str(question_id)), kind, choice_labels
            )
        }
        if option_ids:
            found[str(question_id)] = sorted(option_ids)
    return found


def redact_answers(
    answers: Dict[str, Any], field_ids: Iterable[str], option_ids: Set[str]
) -> int:
    """Replace, in place, the label snapshot of every chosen option of
    ``option_ids`` in the answers to ``field_ids``; returns how many were
    changed (0 when everything is redacted already)."""
    changed = 0
    for field_id in field_ids:
        answer = answers.get(field_id)
        if not isinstance(answer, dict):
            continue
        single = answer.get("choice")
        if (
            isinstance(single, dict)
            and single.get("value") in option_ids
            and single.get("label") != REMOVED_LABEL
        ):
            single["label"] = REMOVED_LABEL
            changed += 1
        multiple = answer.get("choices")
        if isinstance(multiple, dict) and isinstance(multiple.get("values"), list):
            labels = multiple.get("labels")
            if not isinstance(labels, dict):
                labels = {}
                multiple["labels"] = labels
            for value in multiple["values"]:
                if value in option_ids and labels.get(value) != REMOVED_LABEL:
                    labels[value] = REMOVED_LABEL
                    changed += 1
    return changed
