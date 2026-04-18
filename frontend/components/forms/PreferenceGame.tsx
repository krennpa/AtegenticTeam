'use client'

import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Award, Clock3, Flame, Sparkles, Target, Utensils, Wallet } from 'lucide-react'
import { usePreferenceGame } from '../../lib/use-preference-game'
import { PreferenceQuestion } from '../../lib/types'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'

type PreferenceGameProps = {
  questionLimit?: number
  title?: string
  description?: string
}

function prettyToken(value: string): string {
  return value
    .replace(/[_:]/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function getOptionStyle(eventType: PreferenceQuestion['eventType']): string {
  if (eventType === 'veto_card') {
    return 'border-red-200 bg-red-50 text-red-800 hover:bg-red-100'
  }
  if (eventType === 'slider') {
    return 'border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100'
  }
  if (eventType === 'mood_pick') {
    return 'border-cyan-200 bg-cyan-50 text-cyan-900 hover:bg-cyan-100'
  }
  return 'border-sky-200 bg-sky-50 text-sky-900 hover:bg-sky-100'
}

const PREFERENCE_EXAMPLES = [
  {
    title: 'Cuisine Direction',
    description: 'Asian vs Mediterranean or a cuisine to avoid this week.',
    icon: Utensils,
  },
  {
    title: 'Spice Comfort',
    description: 'Mild, medium, or hot based on your current tolerance.',
    icon: Flame,
  },
  {
    title: 'Budget Vibe',
    description: 'Budget, balanced, or premium depending on your week.',
    icon: Wallet,
  },
  {
    title: 'Lunch Pace',
    description: 'Quick break, moderate time, or relaxed long lunch.',
    icon: Clock3,
  },
]

const questionAnimation = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0 },
}

export function PreferenceGame({
  questionLimit = 5,
  title = 'Preference Game',
  description = 'Answer quick prompts so Umamimatch can understand your taste better.',
}: PreferenceGameProps) {
  const [questionIndex, setQuestionIndex] = useState(0)
  const {
    progress,
    questions,
    recommendedAreas,
    loading,
    submittingKey,
    error,
    notice,
    submitAnswer,
    dismissNotice,
  } = usePreferenceGame({ questionLimit })

  const completionWidth = useMemo(
    () => `${Math.max(0, Math.min(100, progress?.completionPercent ?? 0))}%`,
    [progress?.completionPercent]
  )

  useEffect(() => {
    if (questions.length === 0) {
      setQuestionIndex(0)
      return
    }
    if (questionIndex >= questions.length) {
      setQuestionIndex(0)
    }
  }, [questionIndex, questions])

  const activeQuestion = questions[questionIndex]
  const questionStepLabel =
    questions.length > 0 ? `Question ${questionIndex + 1} of ${questions.length}` : null

  const onAnswer = async (question: PreferenceQuestion, answer: string) => {
    const success = await submitAnswer(question, answer, {
      successMessage: 'Saved. Next question ready.',
    })
    if (success) {
      setQuestionIndex((previous) => previous + 1)
    }
  }

  return (
    <section className="relative overflow-hidden rounded-3xl border border-sky-200/60 bg-gradient-to-br from-sky-100 via-white to-amber-100 p-[1px]">
      <div className="pointer-events-none absolute -right-24 -top-24 h-48 w-48 rounded-full bg-sky-200/50 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-16 h-52 w-52 rounded-full bg-amber-200/50 blur-3xl" />

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="relative rounded-[calc(1.5rem-1px)] bg-white/90 p-6 backdrop-blur-sm"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-800">
              <Sparkles className="h-3.5 w-3.5" />
              Interactive
            </div>
            <h2 className="text-2xl font-semibold text-slate-900">{title}</h2>
            <p className="mt-1 text-sm text-slate-600">{description}</p>
          </div>
        </div>

        <div className="mt-6 space-y-5">
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {notice && (
              <motion.button
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                onClick={dismissNotice}
                className="w-full rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-left text-sm text-emerald-800"
              >
                {notice}
              </motion.button>
            )}
          </AnimatePresence>

          {loading && (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
              Loading preference game...
            </div>
          )}

          {!loading && activeQuestion ? (
            <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 px-3 py-6 sm:px-8">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-sky-100 to-transparent" />
              <motion.article
                key={activeQuestion.questionKey}
                variants={questionAnimation}
                initial="hidden"
                animate="visible"
                className="relative mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl"
              >
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary" className="bg-slate-100 text-slate-700">
                      {prettyToken(activeQuestion.area)}
                    </Badge>
                    <Badge variant="outline" className="border-slate-200 text-slate-600">
                      {prettyToken(activeQuestion.eventType)}
                    </Badge>
                  </div>
                  <div className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs text-slate-700">
                    L{progress?.level ?? 1} - {progress?.points ?? 0} pts
                  </div>
                </div>
                {questionStepLabel && (
                  <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">{questionStepLabel}</p>
                )}
                <p className="mb-4 text-base font-medium text-slate-900">{activeQuestion.prompt}</p>
                <div className="flex flex-wrap gap-2">
                  {activeQuestion.options.map((option) => (
                    <Button
                      key={`${activeQuestion.questionKey}-${option.value}`}
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => onAnswer(activeQuestion, option.value)}
                      disabled={submittingKey === activeQuestion.questionKey}
                      className={getOptionStyle(activeQuestion.eventType)}
                    >
                      {option.label}
                    </Button>
                  ))}
                </div>
              </motion.article>
            </div>
          ) : (
            !loading && (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
                No questions available right now. Check back after more activity.
              </div>
            )
          )}

          {!loading && progress && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-2xl border border-slate-200 bg-white p-4"
            >
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-sky-200 bg-sky-50 p-3">
                  <p className="text-xs uppercase tracking-wide text-sky-700">Points</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-900">{progress.points}</p>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                  <p className="text-xs uppercase tracking-wide text-emerald-700">Level</p>
                  <p className="mt-1 flex items-center gap-2 text-2xl font-semibold text-slate-900">
                    <Award className="h-5 w-5 text-emerald-700" />
                    {progress.level}
                  </p>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs uppercase tracking-wide text-amber-700">Completion</p>
                  <p className="mt-1 flex items-center gap-2 text-2xl font-semibold text-slate-900">
                    <Target className="h-5 w-5 text-amber-700" />
                    {progress.completionPercent}%
                  </p>
                </div>
              </div>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: completionWidth }}
                  transition={{ type: 'spring', stiffness: 120, damping: 18 }}
                  className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-500"
                />
              </div>
            </motion.div>
          )}

          {recommendedAreas.length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Recommended Focus</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {recommendedAreas.map((area) => (
                  <Badge key={area} variant="outline" className="border-sky-200 bg-sky-50 text-sky-800">
                    {prettyToken(area)}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Preference Examples</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {PREFERENCE_EXAMPLES.map((example) => {
                const ExampleIcon = example.icon
                return (
                  <div key={example.title} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                      <ExampleIcon className="h-4 w-4 text-sky-700" />
                      {example.title}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">{example.description}</p>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </motion.div>
    </section>
  )
}
