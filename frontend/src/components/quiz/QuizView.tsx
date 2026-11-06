import { useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Trophy,
  XCircle,
} from "lucide-react";
import type { Quiz, QuizAttempt } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useSubmitAttempt } from "@/hooks/useApi";
import { useToast } from "@/components/ui/toast";

interface Props {
  quiz: Quiz;
}

type Phase = "answering" | "submitted";

export function QuizView({ quiz }: Props) {
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [phase, setPhase] = useState<Phase>("answering");
  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const submit = useSubmitAttempt(quiz.lecture_id);
  const { error } = useToast();

  const questions = quiz.questions;
  const current = questions[idx];
  const answeredCount = Object.keys(answers).length;
  const allAnswered = answeredCount === questions.length;

  const score = useMemo(() => {
    if (!attempt) return 0;
    return attempt.score;
  }, [attempt]);

  const select = (optionId: string) => {
    if (phase === "submitted") return;
    setAnswers((a) => ({ ...a, [current.id]: optionId }));
  };

  const onSubmit = async () => {
    try {
      const result = await submit.mutateAsync(answers);
      setAttempt(result);
      setPhase("submitted");
      setIdx(0);
    } catch (err) {
      error("Could not submit quiz", (err as Error).message);
    }
  };

  const retry = () => {
    setAnswers({});
    setAttempt(null);
    setPhase("answering");
    setIdx(0);
  };

  if (phase === "submitted" && attempt) {
    const pct = Math.round((score / attempt.total_questions) * 100);
    return (
      <div className="space-y-5">
        <Card className="border-emerald-200 bg-emerald-50/50">
          <CardContent className="flex flex-col items-center gap-3 p-8 text-center">
            <Trophy className="h-10 w-10 text-emerald-600" />
            <div>
              <p className="text-3xl font-bold text-emerald-700">
                {score} / {attempt.total_questions}
              </p>
              <p className="mt-1 text-sm text-emerald-700/80">
                {pct}% correct
              </p>
            </div>
            <Button variant="secondary" onClick={retry}>
              <RotateCcw className="h-4 w-4" /> Retry quiz
            </Button>
          </CardContent>
        </Card>

        <ol className="space-y-4">
          {questions.map((q) => {
            const given = answers[q.id];
            const correct = q.correct_option;
            const isRight = given === correct;
            return (
              <li
                key={q.id}
                className={cn(
                  "rounded-lg border p-4",
                  isRight ? "border-emerald-200 bg-emerald-50/40" : "border-red-200 bg-red-50/40",
                )}
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <p className="text-sm font-medium text-zinc-900">{q.question}</p>
                  {isRight ? (
                    <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
                  ) : (
                    <XCircle className="h-5 w-5 shrink-0 text-red-600" />
                  )}
                </div>
                <div className="space-y-1.5">
                  {q.options.map((o) => {
                    const isCorrect = o.id === correct;
                    const isGiven = o.id === given;
                    return (
                      <div
                        key={o.id}
                        className={cn(
                          "flex items-start gap-2 rounded-md border px-3 py-2 text-sm",
                          isCorrect && "border-emerald-300 bg-emerald-50 text-emerald-900",
                          isGiven && !isCorrect && "border-red-300 bg-red-50 text-red-900",
                          !isCorrect && !isGiven && "border-zinc-200 bg-white text-zinc-600",
                        )}
                      >
                        <span className="font-semibold">{o.id}.</span>
                        <span className="flex-1">{o.text}</span>
                        {isCorrect && (
                          <span className="text-xs font-medium text-emerald-700">
                            correct
                          </span>
                        )}
                        {isGiven && !isCorrect && (
                          <span className="text-xs font-medium text-red-700">
                            your answer
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 rounded-md bg-white/70 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                    Explanation
                  </p>
                  <p className="mt-1 text-sm text-zinc-700">{q.explanation}</p>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* progress header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Badge className="border-zinc-200 bg-zinc-50 text-zinc-600">
            {answeredCount} / {questions.length} answered
          </Badge>
          {quiz.is_mock && (
            <Badge className="border-amber-200 bg-amber-50 text-amber-700">
              mock quiz
            </Badge>
          )}
        </div>
        <div className="flex gap-1">
          {questions.map((q, i) => (
            <button
              key={q.id}
              onClick={() => setIdx(i)}
              aria-label={`Go to question ${i + 1}`}
              className={cn(
                "h-7 w-7 rounded-md border text-xs font-medium transition-colors",
                i === idx
                  ? "border-primary bg-primary text-white"
                  : answers[q.id]
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-zinc-200 bg-white text-zinc-500 hover:bg-zinc-50",
              )}
            >
              {i + 1}
            </button>
          ))}
        </div>
      </div>

      {/* question card */}
      <Card>
        <CardContent className="p-5">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-500">
              Question {idx + 1} of {questions.length}
            </span>
            <Badge className="border-zinc-200 bg-zinc-50 capitalize text-zinc-500">
              {current.difficulty}
            </Badge>
          </div>
          <p className="mb-4 text-base font-medium leading-relaxed text-zinc-900">
            {current.question}
          </p>

          <div className="space-y-2" role="radiogroup" aria-label="Options">
            {current.options.map((o) => {
              const selected = answers[current.id] === o.id;
              return (
                <button
                  key={o.id}
                  role="radio"
                  aria-checked={selected}
                  onClick={() => select(o.id)}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-md border px-4 py-3 text-left text-sm transition-colors",
                    selected
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50",
                  )}
                >
                  <span
                    className={cn(
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                      selected
                        ? "border-primary bg-primary text-white"
                        : "border-zinc-300 text-zinc-500",
                    )}
                  >
                    {o.id}
                  </span>
                  <span className="text-zinc-700">{o.text}</span>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="secondary"
          disabled={idx === 0}
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
        >
          <ChevronLeft className="h-4 w-4" /> Previous
        </Button>
        {idx < questions.length - 1 ? (
          <Button
            variant="secondary"
            onClick={() => setIdx((i) => Math.min(questions.length - 1, i + 1))}
          >
            Next <ChevronRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button onClick={onSubmit} disabled={!allAnswered || submit.isPending}>
            {submit.isPending ? "Submitting…" : "Submit quiz"}
          </Button>
        )}
      </div>
      {!allAnswered && idx === questions.length - 1 && (
        <p className="text-center text-sm text-zinc-500">
          Answer all questions to submit.
        </p>
      )}
    </div>
  );
}
