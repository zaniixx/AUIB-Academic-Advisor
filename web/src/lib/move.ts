/**
 * F6.1: moving a planned course to another term. The API checks every term the course could go
 * to; these helpers word its answers.
 */
import type { MoveOption, MoveOptions } from "./api";
import { pluralize } from "./format";

/** What a move does to graduation, in a few words. */
export function graduationEffect(option: MoveOption): string {
  const graduation = option.graduation_term?.label;
  if (!graduation) return "Not checked";
  if (option.terms_later === 0) return `Graduation stays ${graduation}`;
  const how = option.terms_later > 0 ? "later" : "earlier";
  return `Graduation ${graduation}, ${pluralize(Math.abs(option.terms_later), "term")} ${how}`;
}

/** The courses besides the moved one whose term changes, as "CSC 422 → Fall 2029". */
export function otherShifts(option: MoveOption, code: string): string[] {
  return option.shifts
    .filter((shift) => shift.code !== code)
    .map((shift) => `${shift.code} → ${shift.after?.label ?? "not planned"}`);
}

/** The check for ``term``, if the API made one. */
export function optionFor(options: MoveOptions | undefined, term: string): MoveOption | undefined {
  return options?.options.find((option) => option.term.label === term);
}
