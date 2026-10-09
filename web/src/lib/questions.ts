/**
 * F2.1: the quick questions about interests, dislikes and plans. The API sends the questions for the
 * student's major; each answer goes into one preference (`interests`, `avoid`, `plans` or `goal`).
 * Two questions can fill `interests`, so each one reads and writes only its own options.
 */
import type { PreferencesIn, Question } from "./api";

type Answers = Pick<PreferencesIn, "interests" | "avoid" | "plans" | "goal">;

function values(preferences: Answers, field: Question["field"]): string[] {
  const value = preferences[field];
  if (Array.isArray(value)) return value;
  return value ? [value] : [];
}

/** What the student picked among this question's options. */
export function selectedIn(question: Question, preferences: Answers): string[] {
  const options = new Set(question.options.map((option) => option.id));
  return values(preferences, question.field).filter((id) => options.has(id));
}

/** The questions to ask now: a follow-up only after one of the answers it follows. */
export function visibleQuestions(questions: Question[], preferences: Answers): Question[] {
  const byId = new Map(questions.map((question) => [question.id, question]));
  return questions.filter((question) => {
    if (!question.show_if) return true;
    const parent = byId.get(question.show_if.question);
    if (!parent) return true;
    return selectedIn(parent, preferences).some((id) => question.show_if!.answers.includes(id));
  });
}

/**
 * The preferences after choosing `optionId`: a multiple-choice option is toggled, a single choice is
 * set. A follow-up that the new answer no longer asks has its answer cleared, so a hidden question
 * cannot still steer the suggestions.
 */
export function answer<T extends Answers>(questions: Question[], question: Question, preferences: T, optionId: string): T {
  let next: T;
  if (question.kind === "multi") {
    const current = values(preferences, question.field);
    const updated = current.includes(optionId) ? current.filter((id) => id !== optionId) : [...current, optionId];
    next = { ...preferences, [question.field]: updated };
  } else {
    next = { ...preferences, [question.field]: optionId };
  }
  const shown = new Set(visibleQuestions(questions, next).map((each) => each.id));
  for (const each of questions) {
    if (!shown.has(each.id) && each.kind === "single" && selectedIn(each, next).length > 0) {
      next = { ...next, [each.field]: null };
    }
  }
  return next;
}
