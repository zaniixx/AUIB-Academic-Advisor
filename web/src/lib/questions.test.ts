import { describe, expect, it } from "vitest";
import type { Question } from "./api";
import { answer, selectedIn, visibleQuestions } from "./questions";

const option = (id: string) => ({ id, label: id });

const QUESTIONS: Question[] = [
  { id: "major_areas", field: "interests", kind: "multi", title: "", hint: "", options: ["ai", "data"].map(option), show_if: null },
  { id: "topics", field: "interests", kind: "multi", title: "", hint: "", options: ["culture", "arts"].map(option), show_if: null },
  { id: "avoid", field: "avoid", kind: "multi", title: "", hint: "", options: ["essays", "math"].map(option), show_if: null },
  { id: "plans", field: "plans", kind: "single", title: "", hint: "", options: ["work", "own_business"].map(option), show_if: null },
  {
    id: "goal",
    field: "goal",
    kind: "single",
    title: "",
    hint: "",
    options: ["software_engineer", "undecided"].map(option),
    show_if: { question: "plans", answers: ["work"] },
  },
];
const [areas, topics, avoid, plans, goal] = QUESTIONS;
const EMPTY = { interests: [] as string[], avoid: [] as string[], plans: null, goal: null };

describe("the quick questions (F2.1)", () => {
  it("keeps two questions that fill interests apart", () => {
    let answers = answer(QUESTIONS, areas, EMPTY, "ai");
    answers = answer(QUESTIONS, topics, answers, "arts");
    expect(answers.interests).toEqual(["ai", "arts"]);
    expect(selectedIn(areas, answers)).toEqual(["ai"]);
    expect(selectedIn(topics, answers)).toEqual(["arts"]);
    answers = answer(QUESTIONS, areas, answers, "ai");
    expect(answers.interests).toEqual(["arts"]);
  });

  it("asks a follow-up only after the answer it follows", () => {
    expect(visibleQuestions(QUESTIONS, EMPTY).map((q) => q.id)).toEqual(["major_areas", "topics", "avoid", "plans"]);
    const working = answer(QUESTIONS, plans, EMPTY, "work");
    expect(visibleQuestions(QUESTIONS, working).map((q) => q.id)).toContain("goal");
  });

  it("forgets the follow-up's answer when the student changes the answer before it", () => {
    let answers = answer(QUESTIONS, plans, EMPTY, "work");
    answers = answer(QUESTIONS, goal, answers, "software_engineer");
    expect(answers.goal).toBe("software_engineer");
    answers = answer(QUESTIONS, plans, answers, "own_business");
    expect(answers.goal).toBeNull();
    expect(answers.plans).toBe("own_business");
  });

  it("toggles what to avoid", () => {
    const answers = answer(QUESTIONS, avoid, answer(QUESTIONS, avoid, EMPTY, "essays"), "math");
    expect(answers.avoid).toEqual(["essays", "math"]);
  });
});
